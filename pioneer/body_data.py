class BodyData:
    def __init__(self, name):
        self.name: str = name
        self.type: str = ''
        self.subclass: str = ''
        self.luminosity: str = ''
        self.terraformable: bool = False
        self.distance: float = 0
        self.base_value: tuple[int, int] = (0, 0)
        self.mapped_value: tuple[float, float] = (1.25, 1.25)
        self.honk_value: tuple[int, int] = (0, 0)
        self.mapped: bool = False
        self.bio_signals: int = 0
        self.is_a_star: bool = False

    def get_name(self):
        return self.name

    def get_base_values(self):
        return self.base_value[0], self.base_value[1]

    def set_base_values(self, value: int, min_value: int):
        self.base_value = (value, min_value)

    def get_mapped_values(self):
        return self.mapped_value[0], self.mapped_value[1]

    def set_mapped_values(self, value: float, min_value: float):
        self.mapped_value = (value, min_value)

    def get_honk_values(self):
        return self.honk_value[0], self.honk_value[1]

    def set_honk_values(self, value: int, min_value: int):
        self.honk_value = (value, min_value)

    def is_mapped(self):
        return self.mapped

    def set_mapped(self, value: bool):
        self.mapped = value

    def get_bio_signals(self):
        return self.bio_signals

    def set_bio_signals(self, value: int):
        self.bio_signals = value

    def get_distance(self):
        return self.distance

    def set_distance(self, value: float):
        self.distance = value

    def get_type(self):
        return self.type

    def set_type(self, value: str):
        self.type = value

    def get_subclass(self):
        return self.subclass

    def set_subclass(self, value: str):
        self.subclass = value

    def get_luminosity(self):
        return self.luminosity

    def set_luminosity(self, value: str):
        self.luminosity = value

    def is_terraformable(self):
        return self.terraformable

    def set_terraformable(self, value: bool):
        self.terraformable = value

    def is_star(self):
        return self.is_a_star

    def set_star(self, value: bool):
        self.is_a_star = value


def get_body_shorthand(body: BodyData):
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
        
    return " [{}]{}".format(tag, " <TC>" if body.is_terraformable() else "")


def get_star_label(star_class: str = "", subclass: str = "", luminosity: str = ""):
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
    elif star_class == "HeBe":
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


def map_edsm_class(edsm_class):
    match edsm_class:
        case 'Earth-like world':
            return 'Earthlike body'
        case 'Metal-rich body':
            return 'Metal rich body'
        case 'High metal content world':
            return 'High metal content body'
        case 'Rocky Ice world':
            return 'Rocky ice body'
        case 'Class I gas giant':
            return 'Sudarsky class I gas giant'
        case 'Class II gas giant':
            return 'Sudarsky class II gas giant'
        case 'Class III gas giant':
            return 'Sudarsky class III gas giant'
        case 'Class IV gas giant':
            return 'Sudarsky class IV gas giant'
        case 'Class V gas giant':
            return 'Sudarsky class V gas giant'
        case 'Gas giant with ammonia-based life':
            return 'Gas giant with ammonia based life'
        case 'Gas giant with water-based life':
            return 'Gas giant with water based life'
        case 'Helium-rich gas giant':
            return 'Helium rich gas giant'
        case _:
            return edsm_class

def parse_edsm_star_class(subtype):
    star_class = ""
    subclass = "0"
    match subtype:
        case 'White Dwarf (D) Star':
            star_class = 'D'
        case 'White Dwarf (DA) Star':
            star_class = 'DA'
        case 'White Dwarf (DAB) Star':
            star_class = 'DAB'
        case 'White Dwarf (DAO) Star':
            star_class = 'DAO'
        case 'White Dwarf (DAZ) Star':
            star_class = 'DAZ'
        case 'White Dwarf (DB) Star':
            star_class = 'DB'
        case 'White Dwarf (DBZ) Star':
            star_class = 'DBZ'
        case 'White Dwarf (DBV) Star':
            star_class = 'DBV'
        case 'White Dwarf (DO) Star':
            star_class = 'DO'
        case 'White Dwarf (DOV) Star':
            star_class = 'DOV'
        case 'White Dwarf (DQ) Star':
            star_class = 'DQ'
        case 'White Dwarf (DC) Star':
            star_class = 'DC'
        case 'White Dwarf (DCV) Star':
            star_class = 'DCV'
        case 'White Dwarf (DX) Star':
            star_class = 'DX'
        case 'CS Star':
            star_class = 'CS'
        case 'C Star':
            star_class = 'C'
        case 'CN Star':
            star_class = 'CN'
        case 'CJ Star':
            star_class = 'CJ'
        case 'CH Star':
            star_class = 'CH'
        case 'CHd Star':
            star_class = 'CHd'
        case 'MS-type Star':
            star_class = 'MS'
        case 'S-type Star':
            star_class = 'S'
        case 'Neutron Star':
            star_class = 'N'
        case 'Black Hole':
            star_class = 'H'
        case 'Supermassive Black Hole':
            star_class = 'SupermassiveBlackHole'

    return star_class, subclass