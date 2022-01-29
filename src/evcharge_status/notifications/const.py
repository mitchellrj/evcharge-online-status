from ..models import ConnectorType, State

CONNECTOR_TYPE_NAME = {
    ConnectorType.UK_3_PIN: 'UK 3-pin plug',
    ConnectorType.CCS: 'CCS',
    ConnectorType.CHADEMO: 'CHAdEmo',
    ConnectorType.TYPE_1: 'Type 1',
    ConnectorType.TYPE_2: 'Type 2',
}

STATE_NAME = {
    State.UNKNOWN: 'Unknown',
    State.AVAILABLE: 'Available',
    State.CHARGING: 'Charging',
}