from enum import Enum


class DeploymentStatus(str, Enum):
    DEPLOYING = "DEPLOYING"
    ACTIVE    = "ACTIVE"
    STOPPED   = "STOPPED"
    FAILED    = "FAILED"