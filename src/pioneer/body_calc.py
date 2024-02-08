def get_starclass_k(star_class: str) -> int:
    if star_class in ['N', 'H', 'SupermassiveBlackHole']:
        return 22628
    elif star_class.startswith('D'):
        return 14057
    else:
        return 1200


def get_planetclass_k(planet_class: str, terraformable: bool) -> tuple[int, int, float]:
    """
        Adapted from MattG's table at https://forums.frontier.co.uk/threads/exploration-value-formulae.232000/
        Thank you, MattG! :)
    """
    terraform = 0
    mult = 1.0  # Multiplier to calculate rough terraform bonus range
    if planet_class == 'Metal rich body':
        base = 21790
    elif planet_class == 'Ammonia world':
        base = 96932
    elif planet_class == 'Sudarsky class I gas giant':
        base = 1656
    elif planet_class == 'Sudarsky class II gas giant' or planet_class == 'High metal content body':
        base = 9654
        if terraformable:
            terraform = 100677
            mult = .9
    elif planet_class == 'Water world':
        base = 64831
        if terraformable:
            terraform = 116295
            mult = .75
    elif planet_class == 'Earthlike body':
        base = 64831 + 116295  # Terraform is assumed as maximum value
        terraform = 0
    else:
        base = 300
        if terraformable:
            terraform = 93328
            mult = .9

    return base, terraform, mult


def get_star_value(k: int, mass: float, first_discoverer: bool) -> tuple[int, int]:
    value = k + (mass * k / 66.25)
    honk_value = value / 3
    if first_discoverer:
        value *= 2.6
        honk_value *= 2.6
    return round(value), round(honk_value)


def get_body_value(k: int, kt: int, tm: float, mass: float, first_discoverer: bool, first_mapper: bool,
                   odyssey_bonus: bool = False) -> tuple[int, int, int, int, int, int]:
    """
        Adapted from MattG's example code at https://forums.frontier.co.uk/threads/exploration-value-formulae.232000/
        Thank you, MattG! :)
    """
    q = 0.56591828
    k_final = k + kt
    k_final_min = k + (kt * tm)

    if first_discoverer and first_mapper:
        mapping_multiplier = 3.699622554
    elif first_mapper:
        mapping_multiplier = 8.0956
    else:
        mapping_multiplier = 10 / 3

    value = (k_final + k_final * q * (mass ** 0.2))
    min_value = (k_final_min + k_final_min * q * (mass ** 0.2))
    mapped_value = value * mapping_multiplier
    min_mapped_value = min_value * mapping_multiplier
    honk_value = value / 3
    min_honk_value = min_value / 3

    # if this.odyssey or this.game_version.major >= 4:
    if odyssey_bonus:
        mapped_value += (mapped_value * 0.3) if (mapped_value * 0.3) > 555 else 555
        min_mapped_value += (min_mapped_value * 0.3) if (min_mapped_value * 0.3) > 555 else 555

    value = value if value > 500 else 500
    min_value = min_value if min_value > 500 else 500
    mapped_value = mapped_value if mapped_value > 500 else 500
    min_mapped_value = min_mapped_value if min_mapped_value > 500 else 500
    honk_value = honk_value if honk_value > 500 else 500
    min_honk_value = min_honk_value if min_honk_value > 500 else 500
    if first_discoverer:
        value *= 2.6
        min_value *= 2.6
        mapped_value *= 2.6
        min_mapped_value *= 2.6
        honk_value *= 2.6
        min_honk_value *= 2.6

    return round(value), round(mapped_value), round(honk_value), \
        round(min_value), round(min_mapped_value), round(min_honk_value)
