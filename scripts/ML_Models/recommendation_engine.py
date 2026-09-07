def get_recommendation(risk, rul):
    
    if rul < 15:
        return "Replace equipment"

    if risk > 0.8:
        return "Schedule maintenance"

    if risk > 0.6:
        return "Inspect equipment"

    return "Continue monitoring"