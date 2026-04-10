class Permission:
    def __init__(self):
        # Dictionary that holds permissions for every action for every user
        self.permissions = {
            "Admin": {
                "can_manage_requests": True,
                "can_submit_request": True,
                "can_view_team": True,
                "can_manage_users": True,
            },
            "Manager": {
                "can_manage_requests": True,
                "can_submit_request": True,
                "can_view_team": True,
                "can_manage_users": False,
            },
            "HR": {
                "can_manage_requests": False,
                "can_submit_request": True,
                "can_view_team": True,
                "can_manage_users": True,
            },
            "Worker": {
                "can_manage_requests": False,
                "can_submit_request": True,
                "can_view_team": False,
                "can_manage_users": False,
            },
        }
#Checks if user has permission to execute command
    def verify_permission(self, role: str, action: str) -> bool:
        """Checks if a role has permission to perform the given action."""
        try:
            return self.permissions[role][action]
        except KeyError:
            print(f"Role \"{role}\" or action \"{action}\" not found.")
            return False

# Space for testing and debugging the code
if __name__ == "__main__":
    permission = Permission()

    roles = ["Admin", "Manager", "HR", "Worker"]
    actions = ["can_manage_requests", "can_submit_request", "can_view_team", "can_manage_users"]

    print(f"{'Role':<12}", end="")
    for action in actions:
        print(f"{action:<25}", end="")
    print()

    for role in roles:
        print(f"{role:<12}", end="")
        for action in actions:
            result = permission.verify_permission(role, action)
            print(f"{'✓' if result else '✗':<25}", end="")
        print()
