from ExploData.explo_data.body_data.struct import PlanetData


def get_body_shorthand(body: PlanetData, commander_id) -> str:
    match body.get_type():
        case 'Icy body':
            tag = "I"
        case 'Rocky body':
            tag = "R"
        case 'Rocky ice body':
            tag = "RI"
        case 'Metal rich body':
            tag = "MR"
        case 'High metal content body':
            tag = "HMC"
        case 'Earthlike body':
            tag = "EL"
        case 'Water world':
            tag = "W"
        case 'Ammonia world':
            tag = "A"
        case 'Water giant':
            tag = "G-W"
        case 'Water giant with life':
            tag = "G-W-L"
        case 'Gas giant with water based life':
            tag = "G-WL"
        case 'Gas giant with ammonia based life':
            tag = "G-AL"
        case 'Sudarsky class I gas giant':
            tag = "G-I"
        case 'Sudarsky class II gas giant':
            tag = "G-II"
        case 'Sudarsky class III gas giant':
            tag = "G-III"
        case 'Sudarsky class IV gas giant':
            tag = "G-IV"
        case 'Sudarsky class V gas giant':
            tag = "G-V"
        case 'Helium rich gas giant':
            tag = "G-He+"
        case 'Helium gas giant':
            tag = "G-He"
        case _:
            tag = ""
        
    return " [{}]{}{}{}".format(
        tag,
        " <TC>" if body.is_terraformable() else "",
        " -S-" if body.was_discovered(commander_id) else "",
        " -M-" if body.was_mapped(commander_id) else ""
    )


def get_star_label(star_class: str = "", subclass: int = 0, luminosity: str = "") -> str:
    name = "Star"
    star_type = "main-sequence"
    if luminosity == "Ia0":
        star_type = "hypergiant"
    elif luminosity.startswith("IV"):
        star_type = "subgiant"
    elif luminosity.startswith("III"):
        star_type = "giant"
    elif luminosity.startswith("II"):
        star_type = "bright giant"
    elif luminosity.startswith("I"):
        star_type = "supergiant"
    if star_class.startswith("D"):
        name = "{}{}white dwarf"
        descriptors = []
        modifier = ""
        if star_class.find("A") is not -1:
            descriptors.append("hydrogen-rich")
        if star_class.find("B") is not -1:
            descriptors.append("helium-rich")
        if star_class.find("C") is not -1:
            descriptors.append("continuous-spectrum")
        if star_class.find("O") is not -1:
            descriptors.append("ionized helium")
        if star_class.find("Q") is not -1:
            descriptors.append("carbon-rich")
        if star_class.find("Z") is not -1:
            descriptors.append("metallic")
        if star_class.find("V") is not -1:
            modifier = "variable"
        if star_class.find("X") is not -1:
            modifier = "atypical"
        name = name.format(modifier + " " if modifier else "",
                           ", ".join(descriptors) + " " if len(descriptors) else "").capitalize()
    elif star_class == "H":
        name = "Black hole"
    elif star_class == "SupermassiveBlackHole":
        star_class = "H"
        name = "Supermassive black hole"
    elif star_class == "N":
        name = "Neutron star"
    elif star_class == "O":
        name = "Luminous blue {} star"
    elif star_class in ["B", "B_BlueWhiteSuperGiant"]:
        star_class = "B"
        name = "Blue {} star"
    elif star_class in ["A", "A_BlueWhiteSuperGiant"]:
        star_class = "A"
        name = "White-blue {} star"
    elif star_class in ["F", "F_WhiteSuperGiant"]:
        star_class = "F"
        name = "White {} star"
    elif star_class in ["G", "G_WhiteSuperGiant"]:
        star_class = "G"
        name = "White-yellow {} star"
    elif star_class in ["K", "K_OrangeGiant"]:
        star_class = "K"
        name = "Yellow-orange {} star"
    elif star_class.startswith("W"):
        name = "{}Wolf-Rayet star"
        descriptor = ""
        if star_class[1:] == "C":
            descriptor = "Carbon-rich "
        elif star_class[1:] == "N":
            descriptor = "Nitrogen and helium-rich "
        elif star_class[1:] == "NC":
            descriptor = "Carbon and nitrogen-rich "
        elif star_class[1:] == "O":
            descriptor = "Carbon and oxygen-rich "
        name = name.format(descriptor)
    elif star_class.startswith("C"):
        name = "{}carbon star"
        descriptor = ""
        if star_class[1:] == "N":
            descriptor = "Bright "
        elif star_class[1:] == "J":
            descriptor = "Carbon-13 rich "
        elif star_class[1:] == "H":
            descriptor = "Metal-poor "
        elif star_class[1:] == "Hd":
            descriptor = "Hydrogen-poor "
        elif star_class[1:] == "S":
            descriptor = "Giant "
        name = name.format(descriptor).capitalize()
    elif star_class in ["M", "M_RedSuperGiant", "M_RedGiant"]:
        star_class = "M"
        if star_type == "main-sequence":
            star_type = "dwarf"
        name = "Red {} star"
    elif star_class == "AeBe":
        name = "Herbig Ae/Be star"
    elif star_class == "TTS":
        name = "T Tauri star"
    elif star_class == "L":
        name = "Dark red dwarf star"
    elif star_class == "T":
        name = "Methane dwarf star"
    elif star_class == "Y":
        name = "Brown dwarf star"
    elif star_class == "MS":
        name = "Intermediate zirconium-monoxide star"
    elif star_class == "S":
        name = "Cool giant zirconium-monoxide star"

    final_name = name.format(star_type)
    return "{} ({}{} {})".format(final_name, star_class, subclass, luminosity)
