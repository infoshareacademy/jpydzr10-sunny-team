class Permission:
    # Dictionary that holds permissions for every action for every user
    permissions = {         "Admin":    {"can_see_all_leave_requests": False,
                                        "can_2": False,
                                        "can_3": False,
                                        "can_4": False},
                            "hr":       {"can_see_all_leave_requests": False,
                                        "can_2": False,
                                        "can_3": False,
                                        "can_4": False},
                            "manager":  {"can_see_all_leave_requests": True,
                                        "can_2": False,
                                        "can_3": False,
                                        "can_4": False},
                            "user":     {"can_see_all_leave_requests": False,
                                        "can_2": False,
                                        "can_3": False,
                                        "can_4": False},
                            "worker":   {"can_see_all_leave_requests": False,
                                        "can_2": False,
                                        "can_3": False,
                                        "can_4": False}}
    # Checks if user has permission to execute command
    @staticmethod
    def verifyPermission(user: str, command: str) -> bool:
        try:
            return Permission.permissions[user][command]
        except KeyError:
            print(f"User with name \"{user}\" was not found")
            return False

# Space for testing and debugging the code
if __name__ == "__main__":


    print("Valid user test: ", Permission.verifyPermission("hr", "can_2"))
    print("Invalid user test: ",Permission.verifyPermission("invalid_user", "can_1"))
