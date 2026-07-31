import * as z from 'zod'

export const PAGE_KEY = '$page'

export const columnSchema = z.object({
  key: z.string().min(1),
  label: z.string(),
  width: z.string().optional(),
  align: z.enum(['left', 'center', 'right']).optional(),
})

export const tableBodySchema = z.object({
  columns: z.array(columnSchema).min(1, 'a table needs at least one column'),
  rows: z.array(z.record(z.string(), z.string())).default([]),
})

export const tableViewSchema = tableBodySchema.extend({
  type: z.literal('table'),
  title: z.string().optional(),
  icon: z.string().optional(),
})

export const viewSchema = z.discriminatedUnion('type', [tableViewSchema])

export const fieldSchema = z.object({
  label: z.string(),
  value: z.string().optional(),
})

export const workflowSectionSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('fields'),
    label: z.string(),
    fields: z.array(fieldSchema).min(1, 'a fields section needs at least one field'),
  }),
  z.object({
    type: z.literal('items'),
    label: z.string(),
    items: z
      .array(z.object({ label: z.string(), icon: z.string().optional() }))
      .min(1, 'an items section needs at least one item'),
  }),
])

const spanSchema = z.enum(['half', 'full']).optional()

export const widgetSchema = z.discriminatedUnion('type', [
  tableBodySchema.extend({
    type: z.literal('table'),
    title: z.string(),
    span: spanSchema,
  }),
  z.object({
    type: z.literal('sections'),
    title: z.string(),
    span: spanSchema,
    sections: z
      .array(workflowSectionSchema)
      .min(1, 'a sections widget needs at least one section'),
  }),
])

export const itemPageSchema = z.object({
  title: z.string(),
  icon: z.string().optional(),
  widgets: z.array(widgetSchema).min(1, 'a page needs at least one widget'),
})

export const navItemSchema = z.object({
  id: z.string().min(1),
  label: z.string(),
  icon: z.string().optional(),
  view: viewSchema,
})

export const navGroupSchema = z.object({
  label: z.string().optional(),
  items: z.array(navItemSchema).min(1, 'a group needs at least one item'),
})

export const sectionSchema = z.object({
  id: z.string().min(1),
  label: z.string(),
  icon: z.string().optional(),
  panel: z.object({
    title: z.string(),
    icon: z.string().optional(),
    groups: z.array(navGroupSchema).min(1, 'a section needs at least one group'),
  }),
})

export const appConfigSchema = z
  .object({
    title: z.string().optional(),
    sections: z.array(sectionSchema).min(1, 'at least one section is required'),
    pages: z.record(z.string(), itemPageSchema).default({}),
  })
  .superRefine((config, ctx) => {
    config.sections.forEach((section, sectionIndex) => {
      section.panel.groups.forEach((group, groupIndex) => {
        group.items.forEach((item, itemIndex) => {
          item.view.rows.forEach((row, rowIndex) => {
            const pageId = row[PAGE_KEY]
            if (!pageId || config.pages[pageId]) return
            ctx.addIssue({
              code: 'custom',
              message: `no page defined with id "${pageId}"`,
              path: [
                'sections',
                sectionIndex,
                'panel',
                'groups',
                groupIndex,
                'items',
                itemIndex,
                'view',
                'rows',
                rowIndex,
                PAGE_KEY,
              ],
            })
          })
        })
      })
    })
  })

export type Column = z.infer<typeof columnSchema>
export type TableView = z.infer<typeof tableViewSchema>
export type View = z.infer<typeof viewSchema>
export type Field = z.infer<typeof fieldSchema>
export type WorkflowSection = z.infer<typeof workflowSectionSchema>
export type Widget = z.infer<typeof widgetSchema>
export type ItemPage = z.infer<typeof itemPageSchema>
export type NavItem = z.infer<typeof navItemSchema>
export type NavGroup = z.infer<typeof navGroupSchema>
export type Section = z.infer<typeof sectionSchema>
export type AppConfig = z.infer<typeof appConfigSchema>

export type ParseResult =
  | { ok: true; config: AppConfig }
  | { ok: false; errors: string[] }

export function parseConfig(input: unknown): ParseResult {
  const result = appConfigSchema.safeParse(input)
  if (result.success) return { ok: true, config: result.data }
  return {
    ok: false,
    errors: result.error.issues.map((issue) => {
      const path = issue.path.length ? issue.path.join('.') : '(root)'
      return `${path}: ${issue.message}`
    }),
  }
}

export function parseConfigText(text: string): ParseResult {
  let json: unknown
  try {
    json = JSON.parse(text)
  } catch (error) {
    return { ok: false, errors: [`Invalid JSON: ${(error as Error).message}`] }
  }
  return parseConfig(json)
}
