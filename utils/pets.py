import time

def get_current_hunger(pet):
    last_fed = pet.get("last_fed", time.time())
    hunger_at_last_fed = pet.get("hunger", 100)
    elapsed = time.time() - last_fed
    decay = (elapsed / 86400) * 10 # -10 hunger every 24 hours
    return max(0, hunger_at_last_fed - decay)

def get_pet_state(pet):
    hunger = get_current_hunger(pet)
    if hunger >= 70:
        return "Well Fed", {}
    elif hunger >= 30:
        return "Hungry", {"xp_penalty": 0.25, "damage_penalty": 0.25}
    elif hunger > 0:
        return "Malnourished", {"blocked": True}
    else:
        return "Starving", {"blocked": True}

def is_pet_dead(pet):
    last_fed = pet.get("last_fed", time.time())
    hunger_at_last_fed = pet.get("hunger", 100)
    
    # If hunger was already 0, starvation_since should be set
    starvation_since = pet.get("starvation_since")
    
    if hunger_at_last_fed > 0:
        # Time it took to reach 0
        time_to_zero = (hunger_at_last_fed / 10) * 86400
        reached_zero_at = last_fed + time_to_zero
    else:
        reached_zero_at = starvation_since or last_fed

    now = time.time()
    if now > reached_zero_at and (now - reached_zero_at) >= (7 * 86400):
        return True
    return False
