import enum

class MissingStrategy(str, enum.Enum):
    DROP_ROWS    = "drop_rows"     # remove rows with missing values
    DROP_COLUMN  = "drop_column"   # remove columns with >50% missing
    MEAN         = "mean"          # fill with column average
    MEDIAN       = "median"        # fill with column middle value
    MODE         = "mode"          # fill with most frequent value
    CONSTANT     = "constant"      # fill with fixed value
    FORWARD_FILL = "forward_fill"  # fill with previous row value

class EncodingMethod(str, enum.Enum):
    LABEL   = "label"    # assign integer to each category
    ONE_HOT = "one_hot"  # create binary column per category
    ORDINAL = "ordinal"  # map to ordered integers manually
    BINARY  = "binary"   # convert to binary columns

class ScalingMethod(str, enum.Enum):
    MIN_MAX   = "min_max"    # scale to [0, 1]
    STANDARD  = "standard"   # mean=0, std=1
    ROBUST    = "robust"     # good with outliers
    LOG       = "log"        # fix skewed distribution

class CleaningVersion(str, enum.Enum):
    V1 = "V1"   # must have: missing, duplicates, types, encoding, scaling
    V2 = "V2"   # nice to have: outliers, imbalanced
    V3 = "V3"   # advanced: SMOTE, KNN imputation