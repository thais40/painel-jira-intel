def extrair_sla_millis(sla_field):
    try:
        if sla_field.get("completedCycles"):
            cycles = sla_field["completedCycles"]
            if isinstance(cycles, list) and cycles:
                return cycles[0].get("elapsedTime", {}).get("millis")
        if sla_field.get("ongoingCycle"):
            return sla_field["ongoingCycle"].get("elapsedTime", {}).get("millis")
    except Exception:
        return None
    return None
