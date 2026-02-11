import { z } from "zod";

export const ArchitectureSchema = z.object({
  system_overview: z.string().min(10),

  component_architecture: z.object({
    frontend: z.object({
      technology: z.string(),
      responsibilities: z.array(z.string())
    }),

    backend_api: z.object({
      framework: z.literal("Django"),
      api_layer: z.literal("Django REST Framework"),
      responsibilities: z.array(z.string())
    }),

    database: z.object({
      engine: z.literal("PostgreSQL"),
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

  phase_1_exclusions: z.array(
    z.object({
      feature: z.string(),
      justification: z.string()
    })
  ),

  extension_hooks: z.array(
    z.object({
      hook_name: z.string(),
      description: z.string()
    })
  ),

  self_evaluation: z.object({
    security: z.number().min(1).max(5),
    simplicity: z.number().min(1).max(5),
    cost_efficiency: z.number().min(1).max(5),
    ownership: z.number().min(1).max(5),
    reversibility: z.number().min(1).max(5),
    notes: z.string()
  }),

  hosting_options: z.array(
    z.object({
      rank: z.number().int().min(1).max(3),
      name: z.string(),
      estimated_monthly_cost: z.string(),
      deployment_model: z.string(),
      pros: z.array(z.string()),
      cons: z.array(z.string())
    })
  ).length(3)
});
