import re

uuid4_pattern = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

def validate_uuid4(uuid4: str):
    return uuid4_pattern.match(uuid4) is not None