import enum


class MissingStrategy(str, enum.Enum):
    median       = "MEDIAN"
    mean         = "MEAN"
    mode         = "MODE"
    drop         = "DROP_ROWS"
    drop_column  = "DROP_COLUMN"
    constant     = "CONSTANT"
    forward_fill = "FORWARD_FILL"


class EncodingMethod(str, enum.Enum):
    one_hot  = "ONE_HOT"
    label    = "LABEL"
    ordinal  = "ORDINAL"
    binary   = "BINARY"
    none     = "none"


class ScalingMethod(str, enum.Enum):
    standard = "STANDARD"
    minmax   = "MIN_MAX"
    robust   = "ROBUST"
    log      = "LOG"
    none     = "none"


class OutlierMethod(str, enum.Enum):
    iqr    = "iqr"
    zscore = "zscore"
    clip   = "clip"
    none   = "none"


class ColumnAction(str, enum.Enum):
    clean  = "clean"
    drop   = "drop"
    target = "target"
    keep   = "keep"


class CleaningStatus(str, enum.Enum):
    pending     = "pending"
    cleaning    = "cleaning"
    ready       = "ready"
    failed      = "failed"
    rolled_back = "rolled_back"