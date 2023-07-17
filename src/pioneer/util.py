from ExploData.explo_data.body_data.struct import PlanetData


def get_body_shorthand(body: PlanetData, commander_id) -> str:
    match body.get_type():
        case 'Icy body':
            tag = 'I'
        case 'Rocky body':
            tag = 'R'
        case 'Rocky ice body':
            tag = 'RI'
        case 'Metal rich body':
            tag = 'MR'
        case 'High metal content body':
            tag = 'HMC'
        case 'Earthlike body':
            tag = 'EL'
        case 'Water world':
            tag = 'W'
        case 'Ammonia world':
            tag = 'A'
        case 'Water giant':
            tag = 'G-W'
        case 'Water giant with life':
            tag = 'G-W-L'
        case 'Gas giant with water based life':
            tag = 'G-WL'
        case 'Gas giant with ammonia based life':
            tag = 'G-AL'
        case 'Sudarsky class I gas giant':
            tag = 'G-I'
        case 'Sudarsky class II gas giant':
            tag = 'G-II'
        case 'Sudarsky class III gas giant':
            tag = 'G-III'
        case 'Sudarsky class IV gas giant':
            tag = 'G-IV'
        case 'Sudarsky class V gas giant':
            tag = 'G-V'
        case 'Helium rich gas giant':
            tag = 'G-He+'
        case 'Helium gas giant':
            tag = 'G-He'
        case _:
            tag = ''
        
    return ' [{}]{}{}{}'.format(
        tag,
        ' <TC>' if body.is_terraformable() else '',
        ' -S-' if body.was_discovered(commander_id) else '',
        ' -M-' if body.was_mapped(commander_id) else ''
    )


def get_star_label(star_class: str = '', subclass: int = 0, luminosity: str = '', show_descriptors: bool = False) -> str:
    name = 'Star'
    star_type = ''
    if luminosity == 'Ia0':
        star_type = 'hypergiant'
    elif luminosity.startswith('VI'):
        star_type = 'compact'
    elif luminosity.startswith('V'):
        star_type = 'main-sequence'
    elif luminosity.startswith('IV'):
        star_type = 'subgiant'
    elif luminosity.startswith('III'):
        star_type = 'giant'
    elif luminosity.startswith('II'):
        star_type = 'bright giant'
    elif luminosity.startswith('I'):
        star_type = 'supergiant'
    if star_class.startswith('D'):
        name = '{}{}white dwarf'
        descriptors = []
        modifier = ''
        if star_class.find('A') is not -1:
            descriptors.append('hydrogen-rich')
        if star_class.find('B') is not -1:
            descriptors.append('helium-rich')
        if star_class.find('C') is not -1:
            descriptors.append('continuous-spectrum')
        if star_class.find('O') is not -1:
            descriptors.append('ionized helium')
        if star_class.find('Q') is not -1:
            descriptors.append('carbon-rich')
        if star_class.find('Z') is not -1:
            descriptors.append('metallic')
        if star_class.find('V') is not -1:
            modifier = 'variable'
        if star_class.find('X') is not -1:
            modifier = 'atypical'
        name = name.format(modifier + ' ' if modifier else '',
                           ', '.join(descriptors) + ' ' if len(descriptors) else '').capitalize()
    elif star_class == 'H':
        name = 'black hole'
        show_descriptors = False
    elif star_class == 'SupermassiveBlackHole':
        star_class = 'H'
        name = 'supermassive black hole'
        show_descriptors = False
    elif star_class == 'N':
        name = 'neutron star'
        show_descriptors = False
    elif star_class == 'O':
        name = 'blue {} star'
    elif star_class in ['B', 'B_BlueWhiteSuperGiant']:
        star_class = 'B'
        name = 'blue-white {} star'
    elif star_class in ['A', 'A_BlueWhiteSuperGiant']:
        star_class = 'A'
        name = 'white-blue {} star'
    elif star_class in ['F', 'F_WhiteSuperGiant']:
        star_class = 'F'
        name = 'white {} star'
    elif star_class in ['G', 'G_WhiteSuperGiant']:
        star_class = 'G'
        name = 'white-yellow {} star'
    elif star_class in ['K', 'K_OrangeGiant']:
        star_class = 'K'
        name = 'yellow-orange {} star'
    elif star_class.startswith('W'):
        name = '{}Wolf-Rayet {} star'
        descriptor = ''
        if star_class[1:] == 'C':
            descriptor = 'carbon-rich '
        elif star_class[1:] == 'N':
            descriptor = 'nitrogen and helium-rich '
        elif star_class[1:] == 'NC':
            descriptor = 'carbon and nitrogen-rich '
        elif star_class[1:] == 'O':
            descriptor = 'carbon and oxygen-rich '
        name = name.format(descriptor, star_type)
    elif star_class.startswith('C'):
        name = '{}{} carbon star'
        descriptor = ''
        if star_class[1:] == 'N':
            descriptor = 'deep red '
        elif star_class[1:] == 'J':
            descriptor = 'carbon-13 rich '
        elif star_class[1:] == 'H':
            descriptor = 'metal-poor '
        elif star_class[1:] == 'Hd':
            descriptor = 'hydrogen-poor '
        elif star_class[1:] == 'S':
            descriptor = 'early-stage '
        elif star_class[1:] == 'R':
            descriptor = 'red '
        name = name.format(descriptor, star_type).capitalize()
    elif star_class in ['M', 'M_RedSuperGiant', 'M_RedGiant']:
        star_class = 'M'
        if star_type == 'main-sequence':
            star_type = 'dwarf'
        if star_type == 'compact':
            star_type = 'subdwarf'
        name = 'red {} star'
    elif star_class == 'AeBe':
        if star_type == 'main-sequence':
            star_type = 'dwarf'
        if star_type == 'compact':
            star_type = 'subdwarf'
        name = 'Herbig Ae/Be {} star'
    elif star_class == 'TTS':
        name = 'T Tauri star'
    elif star_class == 'L':
        if star_type == 'main-sequence':
            star_type = 'dwarf'
        if star_type == 'compact':
            star_type = 'subdwarf'
        name = 'dark red {} star'
    elif star_class == 'T':
        if star_type == 'main-sequence':
            star_type = 'dwarf'
        if star_type == 'compact':
            star_type = 'subdwarf'
        name = 'methane {} star'
    elif star_class == 'Y':
        if star_type == 'main-sequence':
            star_type = 'dwarf'
        if star_type == 'compact':
            star_type = 'subdwarf'
        name = 'brown {} star'
    elif star_class == 'MS':
        name = 'cooling red {} star'
    elif star_class == 'S':
        name = 'cool {} star'

    descriptors = ''
    if show_descriptors:
        luminosity_descriptor = get_luminosity_descriptor(luminosity)
        subclass_descriptor = get_subclass_descriptor(subclass)
        if luminosity_descriptor and subclass_descriptor:
            descriptors = f'{luminosity_descriptor}, {subclass_descriptor}'
        else:
            descriptors = f'{luminosity_descriptor}{subclass_descriptor}'
    final_name = name.format(star_type)
    final_name = final_name[0].upper() + final_name[1:]
    final = '{} ({}{} {}){}'.format(final_name, star_class, subclass, luminosity,
                                    '\n   [{}]'.format(descriptors) if descriptors else '')
    return final


def get_luminosity_descriptor(luminosity: str) -> str:
    if luminosity.endswith('ab'):
        return 'more bright'
    elif luminosity.endswith('a'):
        return 'very bright'
    elif luminosity.endswith('b'):
        return 'dim'
    elif luminosity.endswith('a0'):
        return 'incredibly bright'
    elif luminosity.endswith('z'):
        return 'ionized-helium banding'
    return ''


def get_subclass_descriptor(subclass: int) -> str:
    match subclass:
        case 9:
            return 'low-temp'
        case 7 | 8:
            return 'cooler-temp'
        case 4 | 5 | 6:
            return 'average-temp'
        case 2 | 3:
            return 'warmer-temp'
        case 0 | 1:
            return 'high-temp'
