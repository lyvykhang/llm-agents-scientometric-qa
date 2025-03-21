def delete_keys_from_dict(dictionary: dict, keys: list[str]):
    """
    Helper function for cleaning responses. Deletes specific keys from dictionary values, including nested dictionaries and dictionaries within lists.
    """
    keys_set = set(keys)
    modified_dict = dict()
    for key, value in dictionary.items():
        if key not in keys_set:
            if isinstance(value, dict):
                modified_dict[key] = delete_keys_from_dict(value, keys_set)
            elif isinstance(value, list):
                if len(value) > 0:
                    if isinstance(
                        value[0], dict
                    ):  # Ensure that it's a list of dicts by generalizing the type of the first element.
                        modified_dict[key] = [
                            delete_keys_from_dict(v, keys_set) for v in value
                        ]
                    else:
                        modified_dict[key] = value
                else:
                    modified_dict[key] = value
            else:
                modified_dict[key] = value
    return modified_dict
