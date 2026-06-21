# 🔴 Recursión infinita en políticas RLS de Supabase

## Síntoma

Todas las consultas a `api.bayiva.com/rest/v1/bayiva_*` devuelven **HTTP 500** con el error:

```
infinite recursion detected in policy for relation "bayiva_agencies"
```

Código PostgreSQL: `42P17`

## Causa raíz

Hay un **ciclo de referencia circular** entre las políticas RLS de dos tablas:

### Política 1: `bayiva_agencies` → SELECT (Sebastian)

```sql
CREATE POLICY "bayiva_agencies_select" ON public.bayiva_agencies
  FOR SELECT TO authenticated
  USING (
    (auth.uid() = owner_user_id)
    OR
    -- Subconsulta a bayiva_agency_members →
    (EXISTS (
      SELECT 1 FROM bayiva_agency_members m
      WHERE m.agency_id = m.id          -- ← BUG menor: debería ser bayiva_agencies.id
        AND m.user_id = auth.uid()
    ))
    OR
    is_superadmin()
  );
```

### Política 2: `bayiva_agency_members` → ALL (Sebastian)

```sql
CREATE POLICY "bayiva_agency_members_all" ON public.bayiva_agency_members
  FOR ALL TO authenticated
  USING (
    (EXISTS (
      SELECT 1 FROM bayiva_agencies
      WHERE bayiva_agencies.id = bayiva_agency_members.agency_id
        AND bayiva_agencies.owner_user_id = auth.uid()
    ))
    OR is_superadmin()
  );
```

### Política 3: `bayiva_agency_members` → SELECT (Sebastian)

```sql
CREATE POLICY "bayiva_agency_members_select" ON public.bayiva_agency_members
  FOR SELECT TO authenticated
  USING (
    (user_id = auth.uid())
    OR
    (EXISTS (
      SELECT 1 FROM bayiva_agencies
      WHERE bayiva_agencies.id = bayiva_agency_members.agency_id
        AND bayiva_agencies.owner_user_id = auth.uid()
    ))
    OR is_superadmin()
  );
```

### El ciclo

```
1. Usuario SELECT desde bayiva_agencies
2. → Se evalúa bayiva_agencies_select
3.   → Subconsulta a bayiva_agency_members (línea 8)
4.     → Se evalúa bayiva_agency_members_all o bayiva_agency_members_select
5.       → Subconsulta a bayiva_agencies (línea 22)
6.         → Se evalúa bayiva_agencies_select DE NUEVO → RECURSIÓN 🌀
7.           → PostgreSQL aborta con error 42P17
```

## ¿Por qué pasa?

PostgreSQL **sí aplica RLS en subconsultas dentro de políticas**. Cuando la política de `bayiva_agencies` hace un `SELECT` a `bayiva_agency_members`, se activan las políticas de esa tabla, que a su vez consultan `bayiva_agencies`... y se arma el loop.

## Impacto

- ❌ **portal.bayiva.com**: no carga nada (todas las queries a `bayiva_agencies` fallan)
- ❌ **Cualquier consulta REST** que involucre `bayiva_agencies` desde el frontend
- ✅ **matching.bayiva.com**: funciona (usa SQLite, no Supabase)
- ✅ **Service role** (backend): funciona (bypasea RLS)

## Solución propuesta

La solución mínima es **romper el ciclo** usando una función `SECURITY DEFINER` para la subconsulta a `bayiva_agency_members`. Es una función que hace EXACTAMENTE lo mismo, pero ejecutada con permisos del owner (postgres), por lo que no activa RLS en la tabla referenciada.

```sql
-- Helper que rompe el ciclo de RLS
CREATE OR REPLACE FUNCTION public.is_agency_member()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM bayiva_agency_members m
    WHERE m.user_id = auth.uid()
  );
$$;
```

Y en la política `bayiva_agencies_select`, reemplazar:

```sql
-- ANTES (causa recursión + bug m.agency_id = m.id)
EXISTS (
  SELECT 1 FROM bayiva_agency_members m
  WHERE m.agency_id = m.id AND m.user_id = auth.uid()
)

-- DESPUÉS (rompe el ciclo, lógica equivalente)
is_agency_member()
```

**No se tocan las políticas de `bayiva_agency_members`.** Solo se agrega la función y se modifica UNA línea en `bayiva_agencies_select`.

## Notas adicionales

- `is_superadmin()` ya es `SECURITY DEFINER` (consulta `user_roles` sin activar RLS) — ese patrón funciona bien.
- La función propuesta sigue el mismo patrón.
- `m.agency_id = m.id` en la política original es un bug (compara dos columnas de la misma tabla), pero es irrelevante porque la política nunca llega a ejecutarse correctamente por la recursión.
