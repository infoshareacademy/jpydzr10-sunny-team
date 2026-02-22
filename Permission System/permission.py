class Permission:
    def __init__(self):
        # Dictionary that holds permissions for every action for every user
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
    # Checks if user has permission to execute command
    def verifyPermission(self, user, command):
        try:
            return self.permissions[user][command]
        except KeyError:
            print(f"User with name \"{user}\" was not found")
            return False

# Space for testing and debugging the code
if __name__ == "__main__":

    permission = Permission()

    print("Valid user test: ", permission.verifyPermission("hr", "can_2"))
    print("Invalid user test: ",permission.verifyPermission("invalid_user", "can_1"))
