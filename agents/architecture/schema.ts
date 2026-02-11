import { z } from "zod";

export const ArchitectureSchema = z.object({
  system_overview: z.string(),

  component_architecture: z.object({
    frontend: z.object({
      technology: z.string(),
      responsibilities: z.array(z.string())
    }),
    backend_api: z.object({
      technology: z.string(),
      responsibilities: z.array(z.string())
    }),
    payments: z.object({
      provider: z.string(),
      integration_mode: z.string(),
      pci_scope: z.string()
    })
  }),

  key_decisions: z.array(
    z.object({
      decision: z.string(),
      chosen_because: z.array(z.string()),
      rejected_alternatives: z.array(
        z.object({
          option: z.string(),
          rejected_because: z.string()
        })
      ),
      reversibility: z.string()
    })
  ),

  phase_1_exclusions: z.object({
    excluded_features: z.array(z.string()),
    justification: z.string()
  }),

  extension_hooks: z.object({
    hooks: z.array(z.string())
  }),

  self_evaluation: z.object({
    security: z.number().min(1).max(5),
    simplicity: z.number().min(1).max(5),
    cost_efficiency: z.number().min(1).max(5),
    ownership: z.number().min(1).max(5),
    reversibility: z.number().min(1).max(5),
    notes: z.string()
  })
});

export type ArchitectureOutput = z.infer<typeof ArchitectureSchema>;
