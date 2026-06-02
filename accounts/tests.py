from django.test import TestCase
from accounts.permission import Permission

class PermissionVerifyTest(TestCase):
    #TESTY DLA ADMINA
    def test_Admin_can_approve_request(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_approve_request"))

    def test_Admin_can_reject_request(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_reject_request"))
    
    def test_Admin_can_cancel_request(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_cancel_request"))
    
    def test_Admin_can_change_request(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_change_request"))

    def test_Admin_can_see_all_requests(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_see_all_requests"))

    def test_Admin_can_submit_request(self):
        self.assertFalse(Permission.verifyPermission("Admin","can_submit_request"))
    
    def test_Admin_can_see_own_requests(self):
        self.assertFalse(Permission.verifyPermission("Admin","can_see_own_requests"))
    
    def test_Admin_can_add_user(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_add_user"))
    
    def test_Admin_can_list_users(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_list_users"))

    def test_Admin_can_reset_password(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_reset_password"))

    def test_Admin_can_see_user_vacations(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_see_user_vacations"))
    
    def test_Admin_can_deactivate_staff(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_deactivate_staff"))
    
    def test_Admin_can_deactivate_worker(self):
        self.assertTrue(Permission.verifyPermission("Admin","can_deactivate_worker"))
    
    #TESTY DLA MANAGERA
    
    def test_Manager_can_approve_request(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_approve_request"))

    def test_Manager_can_reject_request(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_reject_request"))
    
    def test_Manager_can_cancel_request(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_cancel_request"))
    
    def test_Manager_can_change_request(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_change_request"))

    def test_Manager_can_see_all_requests(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_see_all_requests"))

    def test_Manager_can_submit_request(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_submit_request"))
    
    def test_Manager_can_see_own_requests(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_see_own_requests"))
    
    def test_Manager_can_add_user(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_add_user"))
    
    def test_Manager_can_list_users(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_list_users"))

    def test_Manager_can_reset_password(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_reset_password"))

    def test_Manager_can_see_user_vacations(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_see_user_vacations"))
    
    def test_Manager_can_deactivate_staff(self):
        self.assertFalse(Permission.verifyPermission("Manager","can_deactivate_staff"))
  
    def test_Manager_can_deactivate_worker(self):
        self.assertTrue(Permission.verifyPermission("Manager","can_deactivate_worker"))
    
    #TESTY DLA HR

    def test_HR_can_approve_request(self):
        self.assertFalse(Permission.verifyPermission("HR","can_approve_request"))

    def test_HR_can_reject_request(self):
        self.assertFalse(Permission.verifyPermission("HR","can_reject_request"))
    
    def test_HR_can_cancel_request(self):
        self.assertTrue(Permission.verifyPermission("HR","can_cancel_request"))
    
    def test_HR_can_change_request(self):
        self.assertFalse(Permission.verifyPermission("HR","can_change_request"))

    def test_HR_can_see_all_requests(self):
        self.assertTrue(Permission.verifyPermission("HR","can_see_all_requests"))

    def test_HR_can_submit_request(self):
        self.assertTrue(Permission.verifyPermission("HR","can_submit_request"))
    
    def test_HR_can_see_own_requests(self):
        self.assertTrue(Permission.verifyPermission("HR","can_see_own_requests"))
    
    def test_HR_can_add_user(self):
        self.assertTrue(Permission.verifyPermission("HR","can_add_user"))
    
    def test_HR_can_list_users(self):
        self.assertTrue(Permission.verifyPermission("HR","can_list_users"))

    def test_HR_can_reset_password(self):
        self.assertFalse(Permission.verifyPermission("HR","can_reset_password"))

    def test_HR_can_see_user_vacations(self):
        self.assertTrue(Permission.verifyPermission("HR","can_see_user_vacations"))
    
    def test_HR_can_deactivate_staff(self):
        self.assertFalse(Permission.verifyPermission("HR","can_deactivate_staff"))
  
    def test_HR_can_deactivate_worker(self):
        self.assertTrue(Permission.verifyPermission("HR","can_deactivate_worker"))

     #TESTY DLA WORKERA

    def test_Worker_can_approve_request(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_approve_request"))

    def test_Worker_can_reject_request(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_reject_request"))
    
    def test_Worker_can_cancel_request(self):
        self.assertTrue(Permission.verifyPermission("Worker","can_cancel_request"))
    
    def test_Worker_can_change_request(self):
        self.assertTrue(Permission.verifyPermission("Worker","can_change_request"))

    def test_Worker_can_see_all_requests(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_see_all_requests"))

    def test_Worker_can_submit_request(self):
        self.assertTrue(Permission.verifyPermission("Worker","can_submit_request"))
    
    def test_Worker_can_see_own_requests(self):
        self.assertTrue(Permission.verifyPermission("Worker","can_see_own_requests"))
    
    def test_Worker_can_add_user(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_add_user"))
    
    def test_Worker_can_list_users(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_list_users"))

    def test_Worker_can_reset_password(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_reset_password"))

    def test_Worker_can_see_user_vacations(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_see_user_vacations"))
    
    def test_Worker_can_deactivate_staff(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_deactivate_staff"))
  
    def test_Worker_can_deactivate_worker(self):
        self.assertFalse(Permission.verifyPermission("Worker","can_deactivate_worker"))
    

