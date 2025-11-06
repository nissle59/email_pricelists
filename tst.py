import crud
from utils.parser_logic import parse

if __name__ == '__main__':
    parse("out.xlsx", days=7)

    # cfgs = crud.list_all_configs()
    # for cfg in cfgs:
    #     for mapping in cfg.mappings:
    #         print(mapping.role.name, mapping.column_name)