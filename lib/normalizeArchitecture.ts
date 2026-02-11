export function normalizeArchitecture(raw: any) {
  const normalized = { ...raw };

  // --------------------------------------------------
  // Normalize component_architecture (legacy tolerance)
  // --------------------------------------------------

  if (raw.component_architecture) {
    const ca = raw.component_architecture;

    // If model returned object but with inconsistent keys,
    // reshape into canonical structure expected by schema.
    if (typeof ca === "object" && !Array.isArray(ca)) {
      normalized.component_architecture = {
        frontend: {
          technology:
            ca.frontend?.technology ||
            ca.storefront_spa?.technology ||
            "React",
          responsibilities:
            ca.frontend?.responsibilities ||
            [ca.storefront_spa?.responsibility].filter(Boolean)
        },

        backend_api: {
          framework: "Django",
          api_layer: "Django REST Framework",
          responsibilities:
            ca.backend_api?.responsibilities ||
            [ca.core_api_service?.responsibility].filter(Boolean)
        },

        database: {
          engine: "PostgreSQL",
          responsibilities:
            ca.database?.responsibilities ||
            [ca.persistence_layer?.responsibility].filter(Boolean)
        },

        payments: {
          provider:
            ca.payments?.provider ||
            "Stripe",
          integration_mode:
            ca.payments?.integration_mode ||
            "hosted_checkout",
          pci_scope:
            ca.payments?.pci_scope ||
            "minimal"
        }
      };
    }
  }

  // --------------------------------------------------
  // Normalize extension_hooks
  // --------------------------------------------------

  if (Array.isArray(raw.extension_hooks)) {
    normalized.extension_hooks = raw.extension_hooks;
  }

  // If object-map form, convert to array
  if (
    raw.extension_hooks &&
    typeof raw.extension_hooks === "object" &&
    !Array.isArray(raw.extension_hooks)
  ) {
    normalized.extension_hooks = Object.entries(raw.extension_hooks).map(
      ([key, value]) => ({
        hook_name: key,
        description: String(value)
      })
    );
  }

  // --------------------------------------------------
  // Normalize hosting_options (safety guard)
  // --------------------------------------------------

  if (Array.isArray(raw.hosting_options)) {
    normalized.hosting_options = raw.hosting_options.map((opt: any) => ({
      rank: Number(opt.rank),
      name: opt.name,
      
	  estimated_monthly_cost:
        typeof opt.estimated_monthly_cost === "number"
          ? `$${opt.estimated_monthly_cost}`
          : String(opt.estimated_monthly_cost),
      deployment_model: opt.deployment_model,
      
	  pros: Array.isArray(opt.pros) ? opt.pros : [],
      cons: Array.isArray(opt.cons) ? opt.cons : []
    }));
  }

  // --------------------------------------------------
  // DO NOT touch:
  // - framework_comparison
  // - key_decisions
  // - self_evaluation
  // - phase_1_exclusions
  // These must match schema exactly.
  // --------------------------------------------------

  return normalized;
}
