"""Scenario Engine exception classes."""


class ScenarioValidationError(Exception):
    def __init__(self, file_path: str, errors: list):
        self.file_path = file_path
        self.errors = errors
        super().__init__(f"Validation failed for {file_path}: {errors}")


class ScenarioFileNotFoundError(Exception):
    def __init__(self, file_path: str):
        self.file_path = file_path
        super().__init__(f"Scenario file not found: {file_path}")


class ScenarioParseError(Exception):
    def __init__(self, file_path: str, detail: str):
        self.file_path = file_path
        self.detail = detail
        super().__init__(f"JSON parse error in {file_path}: {detail}")


class ScenarioNotFoundError(Exception):
    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        super().__init__(f"Scenario not found: {scenario_id}")


class InvalidToggleError(Exception):
    def __init__(self, toggle_id: str, scenario_id: str):
        self.toggle_id = toggle_id
        self.scenario_id = scenario_id
        super().__init__(
            f"Toggle '{toggle_id}' not found in scenario '{scenario_id}'"
        )
