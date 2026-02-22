class Permission:
    def __init__(self):
        self.permissions = {    "Admin":    {"can_1": False,
                                            "can_2": False,
                                            "can_3": False,
                                            "can_4": False},
                                "hr":       {"can_1": False,
                                            "can_2": False,
                                            "can_3": False,
                                            "can_4": False},
                                "manager":  {"can_1": False,
                                            "can_2": False,
                                            "can_3": False,
                                            "can_4": False},
                                "user":     {"can_1": False,
                                            "can_2": False,
                                            "can_3": False,
                                            "can_4": False},
                                "worker":   {"can_1": False,
                                            "can_2": False,
                                            "can_3": False,
                                            "can_4": False}}

    def verifyPermission(self, user, command):
