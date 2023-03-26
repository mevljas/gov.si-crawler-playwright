def extension_to_datatype(extension: str) -> str:
    """
    Converts file extension (.pdf) to DataType enum (PDF).
    """
    return extension[1:].upper()
