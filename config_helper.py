import configparser

def parse_configuration(config_path):
    config_dict = {}
    config = configparser.ConfigParser()
    config.read(config_path)

    for section in config.sections():
        config_dict[section] = parse_configuration_section(config, section)

    return config_dict


def parse_configuration_section(config, section):
    section_dict = {}
    options = config.options(section)
    for option in options:
        try:
            value = config.get(section, option)
            int_value = parse_int(value)
            float_value = parse_float(value)
            if value == 'True':
                section_dict[option] = True
            elif value == 'False':
                section_dict[option] = False
            elif float_value is not None:
                section_dict[option] = float_value
            elif int_value is not None:
                section_dict[option] = int_value
            else:
                section_dict[option] = value
        except:
            print("exception on %s!" % option)
            section_dict[option] = None
    return section_dict


def parse_int(s, base=10, value=None):
    try:
        return int(s, base)
    except ValueError:
        return value


def parse_float(s, value=None):
    if '.' in s:
        try:
            return float(s)
        except ValueError:
            pass
    return value


def parse_tuple(s):
    parts = s.split(",")
    return tuple(parts)



