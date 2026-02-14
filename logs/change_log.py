from datetime import datetime

class ChangeLog:
    """Model zapisywania zmian"""
    def __init__(self,user_id,action,object_type,):
        self.user_id = user_id
        self.action = action
        self.object_type = object_type
        self.date = datetime.now()

class LogHistory:
    def __init__(self):
        self.log_history = []

    def add_new_change(self, user_id, action, object_type):
        new_log = ChangeLog(user_id,action,object_type)
        self.log_history.append(new_log)