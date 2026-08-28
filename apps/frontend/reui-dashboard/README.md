# ReUI Dashboard

z-platform frontend dashboard scaffolded with ReUI patterns.

## Setup

```bash
cd apps/frontend/reui-dashboard
pnpm install
pnpm dev
```

## ReUI Components

Browse the catalog at https://reui.io/components

Install examples:
```bash
npx shadcn add @reui/c-button-10
npx shadcn add @reui/c-data-grid-9
npx shadcn add @reui/c-filters-5
```

## Integration Notes

- Dashboard shell: `app/page.tsx`
- UI primitives: `components/ui/`
- ReUI registry items will be added under `components/reui/`
