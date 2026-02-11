export function normalizeArchitecture(raw: any) {
  const normalized = { ...raw };

  // --- Normalize component_architecture ---
  if (raw.component_architecture) {
    // Case 1: Array-based description
    if (Array.isArray(raw.component_architecture)) {
      const find = (keyword: string) =>
        raw.component_architecture.find(
          (c: any) =>
            typeof c.component === "string" &&
            c.component.toLowerCase().includes(keyword)
        );

      normalized.component_architecture = {
        frontend: {
          technology: "react",
          responsibilities: find("front")
            ? [find("front").responsibility]
            : []
        },
        backend_api: {
          technology: "python",
          responsibilities: find("api") || find("backend")
            ? [find("api")?.responsibility ?? find("backend")?.responsibility]
            : []
        },
        payments: {
          provider: "stripe",
          integration_mode: "hosted_checkout",
          pci_scope: "minimal"
        }
      };
    }

    // Case 2: Object-based description
    if (
      typeof raw.component_architecture === "object" &&
      !Array.isArray(raw.component_architecture)
    ) {
      const values = Object.values(raw.component_architecture) as any[];

      const findTech = (keywords: string[]) =>
        values.find(v =>
          keywords.some(k =>
            String(v.technology).toLowerCase().includes(k)
          )
        );

      normalized.component_architecture = {
        frontend: {
          technology: "react",
          responsibilities: values
            .filter(v =>
              String(v.technology).toLowerCase().includes("react")
            )
            .map(v => v.responsibility)
        },
        backend_api: {
          technology: "python",
          responsibilities: values
            .filter(v =>
              String(v.technology).toLowerCase().includes("django")
            )
            .map(v => v.responsibility)
        },
        payments: {
          provider: "stripe",
          integration_mode: "hosted_checkout",
          pci_scope: "minimal"
        }
      };
    }
  }

  // --- Normalize phase_1_exclusions ---
  if (Array.isArray(raw.phase_1_exclusions)) {
    normalized.phase_1_exclusions = {
      excluded_features: raw.phase_1_exclusions.map(
        (f: any) => f.feature
      ),
      justification:
        "Excluded to enforce Phase-1 scope discipline and minimize complexity."
    };
  }

  // --- Normalize extension_hooks ---
  if (Array.isArray(raw.extension_hooks)) {
    normalized.extension_hooks = {
      hooks: raw.extension_hooks.map(
        (h: any) => h.hook_name
      )
    };
  }

  if (
    raw.extension_hooks &&
    typeof raw.extension_hooks === "object" &&
    !Array.isArray(raw.extension_hooks)
  ) {
    normalized.extension_hooks = {
      hooks: Object.keys(raw.extension_hooks)
    };
  }

  return normalized;
}
