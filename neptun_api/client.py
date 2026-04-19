import requests
import warnings
from datetime import datetime

from .exceptions import NeptunAPIError, NeptunAuthError, NeptunRequestError

OBUDA_BASE = "https://neptun.uni-obuda.hu/ujhallgato/api/"


class NeptunAPI:
    def __init__(self, username: str, password: str, base_url: str = OBUDA_BASE, lcid: int = 1038):
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/") + "/"
        self.lcid = lcid
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"Content-Type": "application/json"})
        self.token: str | None = None
        self.neptun_code: str | None = None
        self._auth_data: dict | None = None
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    # === Core HTTP ===

    def authenticate(self) -> dict:
        url = f"{self.base_url}Account/Authenticate"
        payload = {"userName": self.username, "password": self.password, "lcid": self.lcid}
        try:
            resp = self.session.post(url, json=payload, timeout=30)
        except requests.RequestException as e:
            raise NeptunRequestError(f"Request failed: {e}")
        if resp.status_code == 400:
            data = resp.json()
            errors = data.get("modelStateErrors", [])
            msg = "; ".join(e.get("errors", [""])[0] for e in errors if e.get("errors"))
            raise NeptunAuthError(msg or "Authentication failed", error_data=data)
        if resp.status_code != 200:
            raise NeptunRequestError(f"HTTP {resp.status_code}: {resp.text}")
        data = resp.json().get("data", resp.json())
        self.token = data.get("accessToken")
        self.neptun_code = data.get("neptunCode")
        self._auth_data = data
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        return data

    def refresh_token(self) -> dict:
        data = self._post("Account/GetNewTokens")
        self.token = data.get("accessToken")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        return data

    def logout(self) -> dict:
        return self._post("account/logout")

    def _ensure_auth(self):
        if not self.token:
            self.authenticate()

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        self._ensure_auth()
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=30)
        except requests.RequestException as e:
            raise NeptunRequestError(f"Request failed: {e}")
        if resp.status_code == 401:
            self.authenticate()
            resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            raise NeptunRequestError(f"HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def _post(self, endpoint: str, data: dict | None = None) -> dict:
        self._ensure_auth()
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.post(url, json=data or {}, timeout=30)
        except requests.RequestException as e:
            raise NeptunRequestError(f"Request failed: {e}")
        if resp.status_code == 401:
            self.authenticate()
            resp = self.session.post(url, json=data or {}, timeout=30)
        if resp.status_code == 204:
            return {}
        if resp.status_code != 200:
            raise NeptunRequestError(f"HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def _put(self, endpoint: str, data: dict | None = None) -> dict:
        self._ensure_auth()
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.put(url, json=data or {}, timeout=30)
        except requests.RequestException as e:
            raise NeptunRequestError(f"Request failed: {e}")
        if resp.status_code == 401:
            self.authenticate()
            resp = self.session.put(url, json=data or {}, timeout=30)
        if resp.status_code == 204:
            return {}
        if resp.status_code != 200:
            raise NeptunRequestError(f"HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def _delete(self, endpoint: str, params: dict | None = None) -> dict:
        self._ensure_auth()
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.delete(url, params=params, timeout=30)
        except requests.RequestException as e:
            raise NeptunRequestError(f"Request failed: {e}")
        if resp.status_code == 401:
            self.authenticate()
            resp = self.session.delete(url, params=params, timeout=30)
        if resp.status_code == 204:
            return {}
        if resp.status_code != 200:
            raise NeptunRequestError(f"HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def _data(self, response: dict):
        return response.get("data", response)

    def _paginated(self, endpoint: str, first_row: int = 0, last_row: int = 100, extra_params: dict | None = None):
        params = {"sortAndPage.firstRow": first_row, "sortAndPage.lastRow": last_row}
        if extra_params:
            params.update(extra_params)
        return self._data(self._get(endpoint, params=params))

    # === Raw Access ===

    def raw_get(self, endpoint: str, params: dict | None = None) -> dict:
        return self._get(endpoint, params=params)

    def raw_post(self, endpoint: str, data: dict | None = None) -> dict:
        return self._post(endpoint, data=data)

    def raw_put(self, endpoint: str, data: dict | None = None) -> dict:
        return self._put(endpoint, data=data)

    def raw_delete(self, endpoint: str, params: dict | None = None) -> dict:
        return self._delete(endpoint, params=params)

    # ===================================================================
    # ACCOUNT (9 endpoints)
    # ===================================================================

    def forgotten_password(self, user_name: str, email: str) -> dict:
        return self._data(self._post("Account/ForgottenPassword", data={"userName": user_name, "email": email}))

    def get_forgotten_password_link_is_valid(self, token: str) -> dict:
        return self._data(self._get("Account/GetForgottPasswordLinkIsValid", params={"token": token}))

    def has_user_token_registration(self) -> dict:
        return self._data(self._get("Account/HasUserTokenRegistration"))

    def outer_login(self, token: str) -> dict:
        return self._data(self._post("Account/OuterLogin", data={"token": token}))

    def reset_password(self, data: dict) -> dict:
        return self._data(self._post("Account/ResetPassword", data=data))

    def validate_token_for_forgotten_password(self, token: str) -> dict:
        return self._data(self._get("Account/ValidateTokenForForgottenPassword", params={"token": token}))

    # ===================================================================
    # GENERAL (12 endpoints)
    # ===================================================================

    def get_environment_data(self) -> dict:
        return self._data(self._get("General/EnvironmentData"))

    def get_user_info(self) -> dict:
        return self._data(self._get("UserInfo"))

    def get_user_info_avatar(self) -> dict:
        return self._data(self._get("UserInfo/Avatar"))

    def get_user_avatar(self, image_size_type: int = 1) -> dict:
        return self._data(self._get("General/GetUserAvatar", params={"imageSizeType": image_size_type}))

    def get_users_avatar(self, user_ids: list[str], image_size_type: str = "Thumbnail") -> dict:
        params = {"imageSizeType": image_size_type}
        for i, uid in enumerate(user_ids):
            params[f"userIds[{i}]"] = uid
        return self._data(self._get("General/GetUsersAvatar", params=params))

    def get_default_avatars(self) -> list:
        return self._data(self._get("General/DefaultAvatars"))

    def get_default_fallback_profile_picture_color_codes(self) -> dict:
        return self._data(self._get("General/DefaultFallbackProfilePictureColorCodes"))

    def get_institute(self) -> dict:
        return self._data(self._get("General/Institute"))

    def get_gdpr(self) -> dict:
        return self._data(self._get("MyGdpr"))

    def get_permissions(self) -> dict:
        return self._data(self._get("Permissions", params={"userRoleType": "Hallgatoi"}))

    def get_extended_menu_permissions(self) -> dict:
        return self._data(self._get("ExtendedMenuPermissions"))

    def get_dictionary_item(self, name: str) -> dict:
        return self._data(self._get("General/GetDictionaryItem", params={"name": name}))

    def get_dictionary_item_name(self, name: str) -> dict:
        return self._data(self._get("General/GetDictionaryItemName", params={"name": name}))

    def get_password_expiration(self) -> dict:
        return self._data(self._get("General/GetActiveDomainPasswordExpiration"))

    def get_hweb_error_reporting_email(self) -> dict:
        return self._data(self._get("General/GetHWebErrorReportingEmailSystemParameter"))

    def get_subject_information_in_schedule_planner(self) -> dict:
        return self._data(self._get("General/GetSubjectInformationInSchedulePlanner"))

    def log_ui_error(self, error_data: dict) -> dict:
        return self._data(self._post("General/LogUIError", data=error_data))

    def get_translations(self) -> dict:
        return self._data(self._get("Translations"))

    def set_language(self, lcid: int) -> dict:
        return self._data(self._post("SetLanguage", data={"lcid": lcid}))

    def get_nickname(self) -> dict:
        return self._data(self._get("NickName"))

    def change_password(self, old_password: str, new_password: str) -> dict:
        return self._data(self._post("PasswordChange", data={"oldPassword": old_password, "newPassword": new_password}))

    # ===================================================================
    # TRAININGS (1 endpoint)
    # ===================================================================

    def get_trainings(self) -> list:
        return self._data(self._get("MyTrainings"))

    # ===================================================================
    # AUTHENTICATION / 2FA (4 endpoints)
    # ===================================================================

    def complete_token_registration(self, data: dict) -> dict:
        return self._data(self._post("Authentication/CompleteTokenRegistration", data=data))

    def delete_totp_key(self) -> dict:
        return self._data(self._post("Authentication/DeleteTOTPKey"))

    def get_token_registration_data(self) -> dict:
        return self._data(self._get("Authentication/TokenRegistration/Data"))

    def finish_token_registration(self, data: dict) -> dict:
        return self._data(self._post("Authentication/TokenRegistration/Finish", data=data))

    # ===================================================================
    # DASHBOARD (6 endpoints)
    # ===================================================================

    def get_tasks_count(self) -> dict:
        return self._data(self._get("Dashboard/GetNumberOfTasksByType"))

    def get_threat_lines_count(self) -> int:
        return self._data(self._get("Dashboard/GetThreatLinesCount"))

    def get_average_types_description(self) -> dict:
        return self._data(self._get("Dashboard/GetAverageTypesDescription"))

    def get_dashboard_averages(self) -> dict:
        return self._data(self._get("Dashboard/GetAverages"))

    def get_dashboard_actual_term(self) -> dict:
        return self._data(self._get("dashboard/actualterm"))

    def get_dashboard_credit_progress(self) -> dict:
        return self._data(self._get("dashboard/creditprogress"))

    # ===================================================================
    # MESSAGES (18 endpoints)
    # ===================================================================

    def get_received_messages(self, first_row: int = 0, last_row: int = 20, filter_type: int = 0) -> dict:
        return self._data(self._get("Message/GetReceivedMessages", params={
            "firstRow": first_row, "lastRow": last_row, "filterType": filter_type,
        }))

    def get_sent_messages(self, first_row: int = 0, last_row: int = 20) -> dict:
        return self._data(self._get("Message/GetSentMessages", params={
            "firstRow": first_row, "lastRow": last_row,
        }))

    def get_archived_messages(self, first_row: int = 0, last_row: int = 20) -> dict:
        return self._data(self._get("Message/GetReceivedArchivedMessages", params={
            "firstRow": first_row, "lastRow": last_row,
        }))

    def get_archived_message_posts(self, message_id: str) -> dict:
        return self._data(self._get("Message/GetArchivedMessagePosts", params={"messageId": message_id}))

    def get_unread_message_count(self) -> int:
        return self._data(self._get("Message/GetUnreadedMessagesCount")).get("count", 0)

    def get_mandatory_messages(self) -> list:
        return self._data(self._get("Messages/Mandatories"))

    def get_message_posts(self, message_id: str) -> dict:
        return self._data(self._get(f"Messages/{message_id}/Posts", params={"messageId": message_id}))

    def mark_message_posts_read(self, message_id: str, post_ids: list[str]) -> dict:
        return self._post(f"Messages/{message_id}/Posts/Processed", data={"postIds": post_ids})

    def get_message_settings(self) -> dict:
        return self._data(self._get("Message/GetMessageRelatedSettings"))

    def update_message_settings(self, data: dict) -> dict:
        return self._data(self._post("Message/UpdateMessageRelatedSettings", data=data))

    def get_message_sending_settings(self) -> dict:
        return self._data(self._get("Message/GetMessageSendingSettings"))

    def get_message_limit_setting(self) -> dict:
        return self._data(self._get("Message/GetMessageLimitSetting"))

    def reply_to_post(self, message_id: str, data: dict) -> dict:
        return self._data(self._post("Message/ReplyToPost", data={"messageId": message_id, **data}))

    def add_message_recipients(self, data: dict) -> dict:
        return self._data(self._post("Message/AddMessageRecipients", data=data))

    def remove_message_recipients(self, data: dict) -> dict:
        return self._data(self._post("Message/RemoveMessageRecipients", data=data))

    def close_messages_by_creator(self, data: dict) -> dict:
        return self._data(self._post("Message/CloseMessagesByCreator", data=data))

    def hide_messages_by_recipient(self, data: dict) -> dict:
        return self._data(self._post("Message/HideMessagesByRecipient", data=data))

    def mark_archived_message_posts_read(self, data: dict) -> dict:
        return self._data(self._post("Message/MarkArchivedMessagePostsAsReaded", data=data))

    def skip_required_to_read_messages(self, data: dict) -> dict:
        return self._data(self._post("Message/SkipRequiredToReadMessages", data=data))

    def get_message_pdf(self, message_id: str) -> dict:
        return self._data(self._get("Message/GetMessagePdfForPrint", params={"messageId": message_id}))

    def get_post_pdf(self, post_id: str) -> dict:
        return self._data(self._get("Message/GetPostPdfForPrint", params={"postId": post_id}))

    def download_message_attachments(self, data: dict) -> dict:
        return self._data(self._post("Message/DownloadAttachments", data=data))

    def get_message_documentation_type_ids(self) -> dict:
        return self._data(self._get("Message/GetDocumentationsTypeIds"))

    # ===================================================================
    # TAKEN SUBJECTS (5 endpoints)
    # ===================================================================

    def get_taken_subjects_terms(self) -> list:
        return self._data(self._get("TakenSubjects/Terms"))

    def get_taken_subjects(self, term_id: str, first_row: int = 0, last_row: int = 100, sort: str = "subjectName=asc") -> dict:
        return self._data(self._get("TakenSubjects", params={
            "request.termId": term_id,
            "sortAndPage.firstRow": first_row,
            "sortAndPage.lastRow": last_row,
            f"sortAndPage.{sort.split('=')[0]}": sort.split("=")[1] if "=" in sort else "asc",
        }))

    def get_taken_subjects_data(self, term_id: str) -> dict:
        return self._data(self._get("TakenSubjects/GetTakenSubjects", params={"termId": term_id}))

    def get_taken_subjects_statement_template_ids(self) -> dict:
        return self._data(self._get("TakenSubjects/GetStatementOfTakenSubjectTemplateIds"))

    def get_courses_for_subject_change(self, subject_id: str) -> dict:
        return self._data(self._get("TakenSubjects/GetCoursesOfSignedSubjectForChanging", params={"subjectId": subject_id}))

    def course_change_taken_subject(self, data: dict) -> dict:
        return self._data(self._post("TakenSubjects/CourseChange", data=data))

    # ===================================================================
    # REGISTERED COURSES (2 endpoints)
    # ===================================================================

    def get_registered_courses_terms(self) -> list:
        return self._data(self._get("RegisteredCourses/GetTerms"))

    def get_registered_courses(self, term_id: str, sort: str = "subjectName=asc") -> dict:
        return self._data(self._get("RegisteredCourses/GetRegisteredCourses", params={
            "request.termId": term_id,
            f"sortAndPage.{sort.split('=')[0]}": sort.split("=")[1] if "=" in sort else "asc",
        }))

    # ===================================================================
    # ADVANCEMENT (21 endpoints)
    # ===================================================================

    def get_term_averages(self) -> dict:
        return self._data(self._get("Advancement/GetTermAveragesByTraining"))

    def get_credit_progress(self) -> dict:
        return self._data(self._get("advancement/creditprogress"))

    def get_curriculum_templates(self) -> dict:
        return self._data(self._get("Advancement/GetStudentCurriculumTemplates"))

    def get_certificate_results(self) -> dict:
        return self._data(self._get("Advancement/GetCertificateResults"))

    def get_certificate_result(self, result_id: str) -> dict:
        return self._data(self._get("Advancement/GetCertificateResult", params={"id": result_id}))

    def get_certificate_partial_results(self, result_id: str) -> dict:
        return self._data(self._get("Advancement/GetCertificatePartialResults", params={"id": result_id}))

    def get_current_professions(self) -> dict:
        return self._data(self._get("Advancement/GetCurrentProfessions"))

    def get_current_specializations(self) -> dict:
        return self._data(self._get("Advancement/GetCurrentSpecializations"))

    def get_general_training_data(self) -> dict:
        return self._data(self._get("Advancement/GetGeneralTrainingData"))

    def get_official_records(self) -> dict:
        return self._data(self._get("Advancement/GetOfficialRecords"))

    def get_official_record_details(self, record_id: str) -> dict:
        return self._data(self._get("Advancement/GetOfficialRecordDetails", params={"id": record_id}))

    def get_student_taken_subjects_by_term(self, term_id: str) -> dict:
        return self._data(self._get("Advancement/GetStudentTakenSubjectsByTerm", params={"termId": term_id}))

    def get_student_training_term_data(self, student_training_term_data_id: str) -> dict:
        return self._data(self._get("Advancement/GetStudentTrainingTermData", params={"studentTrainingTermDataId": student_training_term_data_id}))

    def get_student_training_terms(self) -> dict:
        return self._data(self._get("Advancement/GetStudentTrainingTerms"))

    def get_study_details(self) -> dict:
        return self._data(self._get("Advancement/GetStudyDetails"))

    def get_subject_group_data(self, group_id: str) -> dict:
        return self._data(self._get("Advancement/GetSubjectGroupData", params={"id": group_id}))

    def get_training_plan(self) -> dict:
        return self._data(self._get("Advancement/GetTrainingPlan"))

    def get_training_plan_form_type_id(self) -> dict:
        return self._data(self._get("Advancement/GetTrainingPlanFormTypeId"))

    def print_official_entry(self, entry_id: str) -> dict:
        return self._data(self._get("Advancement/PrintOfficialEntry", params={"id": entry_id}))

    def print_training_plan(self) -> dict:
        return self._data(self._get("Advancement/PrintTrainingPlan"))

    # ===================================================================
    # EXAM (19 endpoints)
    # ===================================================================

    def get_exam_terms(self) -> list:
        return self._data(self._get("Exam/GetTerms"))

    def get_exam_detail_conditions(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetExamDetailExamConditions", params={"examId": exam_id}))

    def get_exam_detail_other_info(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetExamDetailOtherInformations", params={"examId": exam_id}))

    def get_exam_previous_history(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetExamPreviousHistoryList", params={"examId": exam_id}))

    def get_exam_room_detail(self, room_id: str) -> dict:
        return self._data(self._get("Exam/GetExamRoomDetail", params={"roomId": room_id}))

    def get_exam_rooms_list(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetExamRoomsList", params={"examId": exam_id}))

    def get_exam_signin_students(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetExamSignInStudentsList", params={"examId": exam_id}))

    def get_exam_tutors(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetExamTutors", params={"examId": exam_id}))

    def get_online_occasions_for_exam(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetOnlineOccasionsForExam", params={"examId": exam_id}))

    def change_exam(self, data: dict) -> dict:
        return self._data(self._post("Exam/ChangeExam", data=data))

    def get_change_exams_list(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetChangeExamsList", params={"examId": exam_id}))

    def get_exam_printable_template_type_id(self) -> dict:
        return self._data(self._get("Exam/GetPrintableTemplateTypeId"))

    def get_exam_request_form_templates_by_subjects(self, term_id: str) -> dict:
        return self._data(self._get("Exam/GetRequestFormTemplateListBySubjects", params={"termId": term_id}))

    def get_exam_request_form_templates_for_signed(self) -> dict:
        return self._data(self._get("Exam/GetRequestFormTemplateListForSignedExams"))

    def get_exam_sent_back_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Exam/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_exam_submitted_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Exam/GetSubmittedRequestFormDetails", params={"id": form_id}))

    def get_exam_submitted_request_forms(self) -> dict:
        return self._data(self._get("Exam/GetSubmittedRequestForms"))

    def get_unipoll_exam_uri(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetUnipollExamUriStudent", params={"examId": exam_id}))

    def get_unipoll_survey_list_for_exam(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetUnipollSurveyListForExam", params={"examId": exam_id}))

    def get_unipoll_survey_list_for_exam_practice(self, exam_id: str) -> dict:
        return self._data(self._get("Exam/GetUnipollSurveyListForExamPractice", params={"examId": exam_id}))

    # ===================================================================
    # EXAM OVERVIEW (4 endpoints)
    # ===================================================================

    def get_available_exams_count(self) -> dict:
        return self._data(self._get("ExamOverview/GetAvailableExamsCount"))

    def get_dashboard_actual_term_exam_entries(self) -> dict:
        return self._data(self._get("ExamOverview/GetDashboardActualTermExamEntries"))

    def get_dashboard_exam_entries(self) -> dict:
        return self._data(self._get("ExamOverview/GetDashboardExamEntries"))

    def get_dashboard_exam_entries_in_actual_term(self) -> dict:
        return self._data(self._get("ExamOverview/GetDashboardExamEntriesInActualTerm"))

    # ===================================================================
    # EXAM REGISTERED EXAMS (2 endpoints)
    # ===================================================================

    def get_registered_exams(self, first_row: int = 0, last_row: int = 9999) -> dict:
        return self._data(self._get("ExamRegisteredExams/GetRegisteredExamsList", params={
            "sortAndPage.firstRow": first_row, "sortAndPage.lastRow": last_row,
        }))

    def get_szev_exam_details_pdf(self, exam_id: str) -> dict:
        return self._data(self._get("ExamRegisteredExams/GetSzevExamDetailsPdf", params={"examId": exam_id}))

    # ===================================================================
    # EXAM REGISTRATION (7 endpoints)
    # ===================================================================

    def get_exam_subjects(self, term_id: str) -> list:
        return self._data(self._get("ExamRegistration/GetExamSubjects", params={"termId": term_id}))

    def get_exam_registration_detail(self, exam_id: str) -> dict:
        return self._data(self._get("ExamRegistration/GetExamRegistrationDetail", params={"examId": exam_id}))

    def get_exams_list(self, subject_id: str, term_id: str) -> dict:
        return self._data(self._get("ExamRegistration/GetExamsList", params={"subjectId": subject_id, "termId": term_id}))

    def sign_up_for_exam(self, data: dict) -> dict:
        return self._data(self._post("ExamRegistration/SignUpForExam", data=data))

    def unsubscribe_from_exam(self, data: dict) -> dict:
        return self._data(self._post("ExamRegistration/UnSubscribe", data=data))

    def get_exam_available_request_form_template(self, template_id: str) -> dict:
        return self._data(self._get("ExamRegistration/GetAvailableRequestFormTemplateDetails", params={"id": template_id}))

    def get_exam_started_request_form_template(self, template_id: str) -> dict:
        return self._data(self._get("ExamRegistration/GetStartedRequestFormTemplateDetails", params={"id": template_id}))

    # ===================================================================
    # EXAM REMAINING EXAMS (2 endpoints)
    # ===================================================================

    def get_remaining_exam_subjects(self, term_id: str) -> dict:
        return self._data(self._get("ExamRemainingExams/GetExamSubjects", params={"termId": term_id}))

    def get_remaining_registered_exams(self) -> dict:
        return self._data(self._get("ExamRemainingExams/GetRemainingRegisteredExamsList"))

    # ===================================================================
    # EXAM RESULTS (4 endpoints)
    # ===================================================================

    def get_exam_results_terms(self) -> dict:
        return self._data(self._get("ExamResults/GetTermsForGetExamResultsList"))

    def get_exam_results_list(self, term_id: str) -> dict:
        return self._data(self._get("ExamResults/GetExamResultsList", params={"termId": term_id}))

    def get_exam_results_detail(self, exam_id: str) -> dict:
        return self._data(self._get("ExamResults/GetExamResultsDetail", params={"examId": exam_id}))

    def get_exam_results_history(self, exam_id: str) -> dict:
        return self._data(self._get("ExamResults/GetExamResultsHistoryList", params={"examId": exam_id}))

    # ===================================================================
    # CALENDAR (29 endpoints)
    # ===================================================================

    def get_calendar_events(
        self,
        start_date: datetime,
        end_date: datetime,
        training_ids: list[str] | None = None,
        display_classes: bool = True,
        display_exams: bool = True,
        display_periods: bool = True,
        display_tasks: bool = True,
        display_online_meetings: bool = True,
        display_other_events: bool = True,
    ) -> list:
        params = {
            "startDate": start_date.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "endDate": end_date.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "displayClasses": str(display_classes).lower(),
            "displayExams": str(display_exams).lower(),
            "displayPeriods": str(display_periods).lower(),
            "displayTasks": str(display_tasks).lower(),
            "displayOnlineMeetings": str(display_online_meetings).lower(),
            "displayOtherEvents": str(display_other_events).lower(),
        }
        if training_ids:
            for i, tid in enumerate(training_ids):
                params[f"studentTrainingIds[{i}]"] = tid
        return self._data(self._get("Calendar/GetCalendarEvents", params=params))

    def get_calendar_trainings(self) -> list:
        return self._data(self._get("Calendar/GetStudentTrainings"))

    def get_calendar_export_links(self) -> dict:
        return self._data(self._get("Calendar/GetLinksForCalendarExport"))

    def generate_new_calendar_export_links(self) -> dict:
        return self._data(self._post("Calendar/GenerateNewLinksForCalendarExport"))

    def get_new_appointment_invitations(self) -> list:
        return self._data(self._get("Calendar/GetNewAllAppointmentInvitations"))

    def get_answered_appointment_invitations(self) -> list:
        return self._data(self._get("Calendar/GetAllAnsweredAppointmentsInvitations"))

    def get_appointment_invitation_details(self, invitation_id: str) -> dict:
        return self._data(self._get("Calendar/GetAppointmentInvitationsDetails", params={"id": invitation_id}))

    def approve_appointment_invitation(self, data: dict) -> dict:
        return self._data(self._post("Calendar/AppointmentApprovalForInvitedUser", data=data))

    def deny_appointment_invitation(self, data: dict) -> dict:
        return self._data(self._post("Calendar/AppointmentDenyForInvitedUser", data=data))

    def get_owner_appointment_details(self, appointment_id: str) -> dict:
        return self._data(self._get("Calendar/GetOwnerAppointmentDetails", params={"id": appointment_id}))

    def insert_appointment_invitation(self, data: dict) -> dict:
        return self._data(self._post("Calendar/InsertAppointmentInvitation", data=data))

    def modify_appointment(self, data: dict) -> dict:
        return self._data(self._post("Calendar/ModifyAppointment", data=data))

    def delete_appointment(self, appointment_id: str) -> dict:
        return self._data(self._post("Calendar/DeleteAppointment", data={"id": appointment_id}))

    def remove_appointment_participant(self, data: dict) -> dict:
        return self._data(self._post("Calendar/RemoveAppointmentParticipant", data=data))

    def get_calendar_course_details(self, event_id: str) -> dict:
        return self._data(self._get("Calendar/GetCourseDetails", params={"id": event_id}))

    def get_calendar_exam_details(self, event_id: str) -> dict:
        return self._data(self._get("Calendar/GetExamDetails", params={"id": event_id}))

    def get_calendar_consultation_details(self, event_id: str) -> dict:
        return self._data(self._get("Calendar/GetConsultationDetails", params={"id": event_id}))

    def get_calendar_holiday_details(self, event_id: str) -> dict:
        return self._data(self._get("Calendar/GetHolidayDetails", params={"id": event_id}))

    def get_calendar_midterm_task_details(self, event_id: str) -> dict:
        return self._data(self._get("Calendar/GetMidTermTaskDetails", params={"id": event_id}))

    def get_calendar_period_details(self, event_id: str) -> dict:
        return self._data(self._get("Calendar/GetPeriodDetails", params={"id": event_id}))

    def get_calendar_subscription_list_details(self, event_id: str) -> dict:
        return self._data(self._get("Calendar/GetSubscriptionListDetails", params={"id": event_id}))

    def get_calendar_appointment_booking_details(self, event_id: str) -> dict:
        return self._data(self._get("Calendar/GetAppointmentBookingDetails", params={"id": event_id}))

    def get_calendar_print_template_ids(self) -> dict:
        return self._data(self._get("Calendar/GetCalendarPrintTemplateIds"))

    def get_institutional_timetables(self, params: dict | None = None) -> dict:
        return self._data(self._get("Calendar/GetInstitutionalTimetables", params=params))

    def get_terms_for_institutional_timetable(self) -> dict:
        return self._data(self._get("Calendar/GetTermsForInstitutionalTimetable"))

    def get_timetable_of_institution(self, params: dict) -> dict:
        return self._data(self._get("Calendar/GetTimetableOfInstitution", params=params))

    def get_calendar_training_name(self, training_id: str) -> dict:
        return self._data(self._get("Calendar/GetTrainingName", params={"studentTrainingId": training_id}))

    def download_filtered_calendar(self, params: dict) -> dict:
        return self._data(self._get("Calendar/CalendarExportFileToDownloadFilteredCalendar", params=params))

    # ===================================================================
    # SUBJECT APPLICATION (18 endpoints)
    # ===================================================================

    def get_subject_application_terms(self) -> dict:
        return self._data(self._get("SubjectApplication/Terms"))

    def get_subject_application_system_params(self) -> dict:
        return self._data(self._get("SubjectApplication/SystemParameters"))

    def get_subject_application_curriculum(self, term_id: str) -> dict:
        return self._data(self._get("SubjectApplication/Curriculum", params={"termId": term_id}))

    def get_subject_application_subject_group(self, params: dict) -> dict:
        return self._data(self._get("SubjectApplication/SubjectGroup", params=params))

    def get_subject_application_subject_types(self) -> dict:
        return self._data(self._get("SubjectApplication/SubjectTypes"))

    def get_schedulable_subjects(self, term_id: str) -> dict:
        return self._data(self._get("SubjectApplication/SchedulableSubjects", params={"termId": term_id}))

    def get_subjects_courses(self, params: dict) -> dict:
        return self._data(self._get("SubjectApplication/GetSubjectsCourses", params=params))

    def get_scheduled_courses(self, term_id: str) -> dict:
        return self._data(self._get("SubjectApplication/GetScheduledCourses", params={"termId": term_id}))

    def get_scheduled_subjects_with_courses(self, term_id: str) -> dict:
        return self._data(self._get("SubjectApplication/ScheduledSubjectsWithScheduledCourses", params={"termId": term_id}))

    def subject_signin(self, data: dict) -> dict:
        return self._data(self._post("SubjectApplication/SubjectSignin", data=data))

    def subject_signout(self, data: dict) -> dict:
        return self._data(self._post("SubjectApplication/SubjectSignout", data=data))

    def schedule_subject_and_courses(self, data: dict) -> dict:
        return self._data(self._post("SubjectApplication/ScheduleSubjectAndCourses", data=data))

    def unschedule_course(self, data: dict) -> dict:
        return self._data(self._post("SubjectApplication/UnScheduleCourse", data=data))

    def delete_all_scheduled_subjects(self, data: dict) -> dict:
        return self._data(self._post("SubjectApplication/DeleteAllScheduledScheduledSubjects", data=data))

    def course_change(self, data: dict) -> dict:
        return self._data(self._post("SubjectApplication/CourseChange", data=data))

    def get_subject_course_locations(self, params: dict) -> dict:
        return self._data(self._get("SubjectApplication/SubjectCourseLocations", params=params))

    def get_languages_for_term(self, term_id: str) -> dict:
        return self._data(self._get("SubjectApplication/LanguagesForGivenTerm", params={"termId": term_id}))

    # ===================================================================
    # SUBJECT COURSE (37 endpoints)
    # ===================================================================

    def get_subject_course_list(self, params: dict) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectCourseList", params=params))

    def get_subject_course_terms(self) -> dict:
        return self._data(self._get("SubjectCourse/GetTerms"))

    def get_subject_details(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectDetails", params={"subjectId": subject_id}))

    def get_course_details(self, course_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCourseDetails", params={"courseId": course_id}))

    def get_courses_by_subject_id(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCoursesBySubjectId", params={"subjectId": subject_id}))

    def get_courses_by_subject_from_list(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCoursesBySubjectIdFromSubjectCourseList", params={"subjectId": subject_id}))

    def get_course_tab_details(self, course_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCourseTabDetails", params={"courseId": course_id}))

    def get_course_class_instance_details(self, instance_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCourseClassInstanceDetails", params={"id": instance_id}))

    def get_course_class_instance_room_list(self, instance_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCourseClassInstanceDetailsRoomList", params={"id": instance_id}))

    def get_course_class_instance_room_item(self, room_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCourseClassInstanceRoomItemDetails", params={"roomId": room_id}))

    def get_course_connected_subjects(self, course_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCourseConnectedSubjects", params={"courseId": course_id}))

    def get_course_timetable_details(self, course_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCourseTimetableDetails", params={"courseId": course_id}))

    def get_course_timetable_attendance_sum(self, course_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetCourseTimetableAttendanceSum", params={"courseId": course_id}))

    def get_subject_course_curriculum_templates(self) -> dict:
        return self._data(self._get("SubjectCourse/GetCurriculumTemplates"))

    def get_general_requirements(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetGeneralRequirements", params={"subjectId": subject_id}))

    def get_administrative_org_units(self, params: dict | None = None) -> dict:
        return self._data(self._get("SubjectCourse/GetAdministrativeOrganizationalUnits", params=params))

    def get_administrative_org_unit_type_filter(self) -> dict:
        return self._data(self._get("SubjectCourse/GetAdministrativeOrganizationalUnitTypeFilter"))

    def get_organizational_units(self, params: dict | None = None) -> dict:
        return self._data(self._get("SubjectCourse/GetOrganizationalUnits", params=params))

    def get_organizational_unit_type_filter(self) -> dict:
        return self._data(self._get("SubjectCourse/GetOrganizationalUnitTypeFilter"))

    def get_ranking_on_course(self, course_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetRankingOnCourse", params={"courseId": course_id}))

    def get_referenced_subjects(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetReferencedSubjects", params={"subjectId": subject_id}))

    def get_subject_course_notes(self, params: dict) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectCourseNotes", params=params))

    def get_subject_course_students(self, course_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectCourseStudents", params={"courseId": course_id}))

    def get_subject_course_tutors(self, course_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectCourseTutors", params={"courseId": course_id}))

    def get_subject_groups(self) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectGroups"))

    def get_subject_prerequirements(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectPrerequirements", params={"subjectId": subject_id}))

    def get_subject_prerequirement_details(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectPrerequirementDetails", params={"subjectId": subject_id}))

    def get_subject_prerequirement_subjects(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectPrerequirementSubjects", params={"subjectId": subject_id}))

    def get_subject_result(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectResult", params={"subjectId": subject_id}))

    def get_subject_results_list(self, term_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectResultsList", params={"termId": term_id}))

    def get_subject_results_list_terms(self) -> dict:
        return self._data(self._get("SubjectCourse/GetTermsForSubjectResultsList"))

    def get_subject_students(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectStudents", params={"subjectId": subject_id}))

    def get_subject_topic_list(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectTopicList", params={"subjectId": subject_id}))

    def get_subject_topic_details(self, topic_id: str) -> dict:
        return self._data(self._get("SubjectCourse/GetSubjectTopicDetails", params={"topicId": topic_id}))

    def rate_subject(self, data: dict) -> dict:
        return self._data(self._post("SubjectCourse/RateSubject", data=data))

    # ===================================================================
    # SUBJECT EQUIVALENCE (5 endpoints)
    # ===================================================================

    def get_inner_subjects_equivalence(self) -> dict:
        return self._data(self._get("SubjectEquivalence/GetInnerSubjectsEquivalenceData"))

    def get_inner_subjects_equivalence_detail(self, equivalence_id: str) -> dict:
        return self._data(self._get("SubjectEquivalence/GetInnerSubjectsEquivalenceDetailData", params={"id": equivalence_id}))

    def get_outer_subjects_equivalence(self) -> dict:
        return self._data(self._get("SubjectEquivalence/GetOuterSubjectsEquivalenceData"))

    def get_outer_subjects_equivalence_detail(self, equivalence_id: str) -> dict:
        return self._data(self._get("SubjectEquivalence/GetOuterSubjectsEquivalenceDetailData", params={"id": equivalence_id}))

    def get_outer_subjects_equivalence_organizations(self) -> dict:
        return self._data(self._get("SubjectEquivalence/GetOuterSubjectsEquivalenceOrganizationData"))

    # ===================================================================
    # SUBJECT RELATED REQUEST FORM (8 endpoints)
    # ===================================================================

    def get_subject_related_fillable_request_forms(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectRelatedRequestForm/GetSubjectRelatedFillableRequestForms", params={"subjectId": subject_id}))

    def get_curriculum_templates_for_subject(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectRelatedRequestForm/GetCurriculumTemplatesForSubject", params={"subjectId": subject_id}))

    def get_fillable_request_form_types_for_subject(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectRelatedRequestForm/GetFillableRequestFormTemplateTypesForSubject", params={"subjectId": subject_id}))

    def get_inner_subject_equivalence_rules(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectRelatedRequestForm/GetInnerSubjectEquivalenceRulesForSubject", params={"subjectId": subject_id}))

    def get_outer_subject_equivalence_rules(self, subject_id: str) -> dict:
        return self._data(self._get("SubjectRelatedRequestForm/GetOuterSubjectEquivalenceRulesForSubject", params={"subjectId": subject_id}))

    def get_subject_related_sent_back_request(self, form_id: str) -> dict:
        return self._data(self._get("SubjectRelatedRequestForm/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_subject_related_submitted_request(self, form_id: str) -> dict:
        return self._data(self._get("SubjectRelatedRequestForm/GetSubmittedRequestFormDetails", params={"id": form_id}))

    def get_subject_related_submitted_requests(self) -> dict:
        return self._data(self._get("SubjectRelatedRequestForm/GetSubmittedRequestForms"))

    # ===================================================================
    # CURRICULUM (12 endpoints)
    # ===================================================================

    def get_curriculum_completable_subjects(self, curriculum_id: str) -> dict:
        return self._data(self._get("Curriculum/GetCompletableCurriculumSubjects", params={"curriculumId": curriculum_id}))

    def get_curriculum_subject_group_data(self, params: dict) -> dict:
        return self._data(self._get("Curriculum/GetCurriculumSubjectGroupAndSubjectsData", params=params))

    def get_curriculum_subjects_by_term(self, params: dict) -> dict:
        return self._data(self._get("Curriculum/GetCurriculumSubjectsByTermData", params=params))

    def get_milestones_by_curriculum(self) -> dict:
        return self._data(self._get("Curriculum/GetMileStonesListByCurriculums"))

    def get_optional_subjects_summary(self) -> dict:
        return self._data(self._get("Curriculum/GetOptionalSubjectsSummary"))

    def get_optional_subjects_without_curriculum(self) -> dict:
        return self._data(self._get("Curriculum/GetOptionalSubjectsWithoutCurriculum"))

    def get_student_curriculum_templates_v2(self) -> dict:
        return self._data(self._get("Curriculum/GetStudentCurriculumTemplates"))

    def get_student_curriculum_templates_base_data(self) -> dict:
        return self._data(self._get("Curriculum/GetStudentCurriculumTemplatesBaseData"))

    def get_student_curriculum_templates_for_milestones(self) -> dict:
        return self._data(self._get("Curriculum/GetStudentCurriculumTemplatesForMilestones"))

    def get_student_hierarchical_advancements(self) -> dict:
        return self._data(self._get("Curriculum/GetStudentHierarchicalAdvancements"))

    def get_subject_groups_by_curriculum(self, curriculum_id: str) -> dict:
        return self._data(self._get("Curriculum/GetSubjectGroupsAndSubjectsByCurriculumTemplate", params={"curriculumId": curriculum_id}))

    # ===================================================================
    # FINANCIAL DATA DASHBOARD (3 endpoints) — already exists
    # ===================================================================

    def get_financial_dashboard_visibility(self) -> dict:
        return self._data(self._get("FinancialDataDashboard/GetDashboardElementsVisibility"))

    def get_financial_impositions(self) -> dict:
        return self._data(self._get("FinancialDataDashboard/GetDashboardImpostionBlockLeft"))

    def get_collective_invoices(self) -> dict:
        return self._data(self._get("FinancialDataDashboard/GetCollectiveInvoices"))

    # ===================================================================
    # FINANCIAL ITEM (15 endpoints)
    # ===================================================================

    def get_student_impositions(self, term_id: str | None = None) -> dict:
        params = {"termId": term_id} if term_id else {}
        return self._data(self._get("FinancialItem/GetStudentImpositions", params=params))

    def get_financial_item_terms(self) -> dict:
        return self._data(self._get("FinancialItem/GetTermsForGetStudentImpositions"))

    def get_financial_item_data(self, item_id: str) -> dict:
        return self._data(self._get("FinancialItem/GetFinancialItemData", params={"id": item_id}))

    def get_financial_item_detail(self, item_id: str) -> dict:
        return self._data(self._get("FinancialItem/GetFinancialItemDetail", params={"id": item_id}))

    def get_deleted_impositions(self) -> dict:
        return self._data(self._get("FinancialItem/GetDeletedImpositions"))

    def get_deleted_imposition_details(self, imposition_id: str) -> dict:
        return self._data(self._get("FinancialItem/GetDeletedImpositionDetails", params={"id": imposition_id}))

    def get_items_to_be_payed(self) -> dict:
        return self._data(self._get("FinancialItem/GetItemsToBePayed"))

    def delete_items_to_be_payed(self, data: dict) -> dict:
        return self._data(self._post("FinancialItem/DeleteItemsToBePayed", data=data))

    def get_allowed_payment_methods(self) -> dict:
        return self._data(self._get("FinancialItem/GetAllowedPaymentMethods"))

    def get_payment_types_for_impositions(self) -> dict:
        return self._data(self._get("FinancialItem/GetPaymentTypesForStudentImpositions"))

    def check_financial_item_print(self, item_id: str) -> dict:
        return self._data(self._get("FinancialItem/CheckFinancialItemPrint", params={"id": item_id}))

    def print_financial_item(self, item_id: str) -> dict:
        return self._data(self._get("FinancialItem/PrintFinancialItem", params={"id": item_id}))

    def check_pay_in_conditions(self, data: dict) -> dict:
        return self._data(self._post("FinancialItem/CheckPayInConditions", data=data))

    def check_impositions_with_student_loan(self) -> dict:
        return self._data(self._get("FinancialItem/CheckImpositionsWithStudentLoan"))

    def sign_impositions_with_student_loan(self, data: dict) -> dict:
        return self._data(self._post("FinancialItem/SignImpositionsWithStudentLoan", data=data))

    # ===================================================================
    # FINANCIAL BONUSES (3 endpoints)
    # ===================================================================

    def get_student_financial_bonuses(self) -> dict:
        return self._data(self._get("FinancialBonuses/GetStudentFinancialBonuses"))

    def get_student_bonus_details(self, bonus_id: str) -> dict:
        return self._data(self._get("FinancialBonuses/GetStudentBonusDetails", params={"id": bonus_id}))

    def get_financial_bonuses_terms(self) -> dict:
        return self._data(self._get("FinancialBonuses/GetTermsForStudentFinancialBonusesTermFilter"))

    # ===================================================================
    # FINANCIAL OPTIONS (9 endpoints)
    # ===================================================================

    def get_health_fund_data(self) -> dict:
        return self._data(self._get("FinancialOptions/GetHealthFundData"))

    def set_health_fund_data(self, data: dict) -> dict:
        return self._data(self._post("FinancialOptions/SetHealthFundData", data=data))

    def delete_health_fund_data(self) -> dict:
        return self._data(self._post("FinancialOptions/DeleteHealthFundData"))

    def get_student_loan(self) -> dict:
        return self._data(self._get("FinancialOptions/GetStudentLoan"))

    def set_student_loan(self, data: dict) -> dict:
        return self._data(self._post("FinancialOptions/SetStudentLoan", data=data))

    def delete_student_loan(self) -> dict:
        return self._data(self._post("FinancialOptions/DeleteStudentLoan"))

    def get_student_loan2_data(self) -> dict:
        return self._data(self._get("FinancialOptions/GetStudentLoan2Data"))

    def get_student_pension_data(self) -> dict:
        return self._data(self._get("FinancialOptions/GetStudentPensionData"))

    def set_student_pension(self, data: dict) -> dict:
        return self._data(self._post("FinancialOptions/SetStudentPension", data=data))

    def delete_student_pension(self) -> dict:
        return self._data(self._post("FinancialOptions/DeleteStudentPension"))

    # ===================================================================
    # FINANCIAL DATA (2 endpoints)
    # ===================================================================

    def get_fair_pay_data_transfer_form(self) -> dict:
        return self._data(self._get("FinancialData/GetFairPayDataTransferFormData"))

    def get_student_pay_in_imposition_details(self, imposition_id: str) -> dict:
        return self._data(self._get("FinancialData/GetStudentPayInImpositionDetails", params={"id": imposition_id}))

    # ===================================================================
    # FINANCIAL DATA REQUEST FORM (6 endpoints)
    # ===================================================================

    def get_financial_available_request_form(self, template_id: str) -> dict:
        return self._data(self._get("FinancialDataRequestForm/GetAvailableRequestFormTemplateDetails", params={"id": template_id}))

    def get_financial_request_form_template_list(self) -> dict:
        return self._data(self._get("FinancialDataRequestForm/GetRequestFormTemplateList"))

    def get_financial_sent_back_request_form(self, form_id: str) -> dict:
        return self._data(self._get("FinancialDataRequestForm/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_financial_started_request_form(self, form_id: str) -> dict:
        return self._data(self._get("FinancialDataRequestForm/GetStartedRequestFormDetails", params={"id": form_id}))

    def get_financial_submitted_request_form(self, form_id: str) -> dict:
        return self._data(self._get("FinancialDataRequestForm/GetSubmittedRequestFormDetails", params={"id": form_id}))

    def get_financial_submitted_request_forms(self) -> dict:
        return self._data(self._get("FinancialDataRequestForm/GetSubmittedRequestForms"))

    # ===================================================================
    # COLLECTIVE INVOICES (9 endpoints)
    # ===================================================================

    def get_collective_invoice_detail(self, invoice_id: str) -> dict:
        return self._data(self._get("CollectiveInvoices/GetCollectiveInvoiceDetail", params={"id": invoice_id}))

    def get_collective_invoice_list_for_pay_in(self) -> dict:
        return self._data(self._get("CollectiveInvoices/GetCollectiveInvoiceListForPayIn"))

    def get_collective_invoices_list(self) -> dict:
        return self._data(self._get("CollectiveInvoices/GetCollectiveInvoicesList"))

    def get_previous_transactions_from_collective_invoice(self, invoice_id: str) -> dict:
        return self._data(self._get("CollectiveInvoices/GetPreviousTransactionsListFromCollectiveInvoice", params={"id": invoice_id}))

    def get_refund_from_collective_invoice(self, invoice_id: str) -> dict:
        return self._data(self._get("CollectiveInvoices/GetRefoundFromCollectiveInvoice", params={"id": invoice_id}))

    def get_bank_accounts_for_collective_invoice(self, invoice_id: str) -> dict:
        return self._data(self._get("CollectiveInvoices/GetStudentsBankAccountsListForCollectiveInvoice", params={"id": invoice_id}))

    def pay_in_with_collective_invoice(self, data: dict) -> dict:
        return self._data(self._post("CollectiveInvoices/PayInWithCollectiveInvoice", data=data))

    def refund_from_collective_invoice(self, data: dict) -> dict:
        return self._data(self._post("CollectiveInvoices/RefoundFromCollectiveInvoice", data=data))

    def save_collective_invoice_detail(self, data: dict) -> dict:
        return self._data(self._post("CollectiveInvoices/SaveCollectiveInvoiceDetail", data=data))

    # ===================================================================
    # INSERT IMPOSITION (6 endpoints)
    # ===================================================================

    def get_insert_imposition_terms(self) -> dict:
        return self._data(self._get("InsertImposition/GetTerms"))

    def get_insert_imposition_subjects(self, term_id: str) -> dict:
        return self._data(self._get("InsertImposition/GetSubjects", params={"termId": term_id}))

    def get_service_titles_list(self) -> dict:
        return self._data(self._get("InsertImposition/GetServiceTitlesList"))

    def check_payment_title_type(self, data: dict) -> dict:
        return self._data(self._post("InsertImposition/CheckPaymentTitleType", data=data))

    def create_imposition_reexamination_fee(self, data: dict) -> dict:
        return self._data(self._post("InsertImposition/CreateNewImpositionReExaminationFee", data=data))

    def save_imposition_service_title(self, data: dict) -> dict:
        return self._data(self._post("InsertImposition/SaveImpositionServiceTitle", data=data))

    # ===================================================================
    # IMPOSITION SHARE AND COLLAPSE (3 endpoints)
    # ===================================================================

    def get_collapsable_impositions(self) -> dict:
        return self._data(self._get("ImpositionShareAndCollapse/GetCollapsableImpositions"))

    def collapse_impositions(self, data: dict) -> dict:
        return self._data(self._post("ImpositionShareAndCollapse/CollapseImpositions", data=data))

    def share_imposition(self, data: dict) -> dict:
        return self._data(self._post("ImpositionShareAndCollapse/ShareImposition", data=data))

    # ===================================================================
    # IMPOSITION STATEMENT (3 endpoints)
    # ===================================================================

    def get_imposition_statements(self) -> dict:
        return self._data(self._get("ImpositionStatement/GetImpositionStatements"))

    def get_initial_data_for_imposition_statement(self) -> dict:
        return self._data(self._get("ImpositionStatement/GetInitialDataForImpositionStatement"))

    def save_imposition_statement_status(self, data: dict) -> dict:
        return self._data(self._post("ImpositionStatement/SaveImpositionStatementStatus", data=data))

    # ===================================================================
    # INVOICES (3 endpoints)
    # ===================================================================

    def get_invoices_for_student(self) -> dict:
        return self._data(self._get("Invoices/GetInvoicesForStudent"))

    def get_invoice_details(self, invoice_id: str) -> dict:
        return self._data(self._get("Invoices/GetInvoiceDetailsForStudent", params={"id": invoice_id}))

    def download_invoice_attachment(self, attachment_id: str) -> dict:
        return self._data(self._get("Invoices/DownloadInvoiceAttachment", params={"id": attachment_id}))

    # ===================================================================
    # TRANSACTIONS (5 endpoints)
    # ===================================================================

    def get_student_previous_transactions(self, params: dict | None = None) -> dict:
        return self._data(self._get("Transactions/GetStudentPreviousTransactions", params=params))

    def get_student_previous_transactions_filters(self) -> dict:
        return self._data(self._get("Transactions/GetStudentPreviousTransactionsFilters"))

    def get_student_previous_transaction_types_filter(self) -> dict:
        return self._data(self._get("Transactions/GetStudentPreviousTransactionTypesFilter"))

    def get_student_transaction_details(self, transaction_id: str) -> dict:
        return self._data(self._get("Transactions/GetStudentTransactionDetails", params={"id": transaction_id}))

    def get_transaction_paying_type_filter_from_collective_invoice(self, invoice_id: str) -> dict:
        return self._data(self._get("Transactions/GetTransactionPayingTypeFilterFromCollectiveInvoice", params={"id": invoice_id}))

    # ===================================================================
    # SIMPLE PAY (4 endpoints)
    # ===================================================================

    def get_simple_pay_data(self) -> dict:
        return self._data(self._get("SimplePay/GetSimplePayDataTransferFormData"))

    def simple_pay_has_default_email(self) -> dict:
        return self._data(self._get("SimplePay/HasDefaultEmailAddress"))

    def simple_pay_start_payment(self, data: dict) -> dict:
        return self._data(self._post("SimplePay/StartPayment", data=data))

    def simple_pay_handle_result(self, data: dict) -> dict:
        return self._data(self._post("SimplePay/HandlePaymentResult", data=data))

    # ===================================================================
    # FAIR PAY (1 endpoint)
    # ===================================================================

    def fair_pay_validate_and_send(self, data: dict) -> dict:
        return self._data(self._post("FairPay/ValidateAndSendPaymentRequest", data=data))

    # ===================================================================
    # BANK ACCOUNT (17 endpoints)
    # ===================================================================

    def get_bank_accounts(self) -> dict:
        return self._data(self._get("BankAccount/GetBankAccounts"))

    def get_bank_account_details(self, account_id: str) -> dict:
        return self._data(self._get("BankAccount/GetBankAccountDetails", params={"id": account_id}))

    def get_bank_account_modify_data(self, account_id: str) -> dict:
        return self._data(self._get("BankAccount/GetBankAccountModifyData", params={"id": account_id}))

    def get_bank_account_documentation_types(self) -> dict:
        return self._data(self._get("BankAccount/GetBankAccountDocumentationTypes"))

    def get_bank_account_tab_list(self) -> dict:
        return self._data(self._get("BankAccount/GetUserBankAccountTabList"))

    def get_default_bank_account_number(self) -> dict:
        return self._data(self._get("BankAccount/GetDefaultBankAccountNumber"))

    def get_can_upload_bank_documentation(self) -> dict:
        return self._data(self._get("BankAccount/GetCanUploadDocumentation"))

    def get_bank_countries(self) -> dict:
        return self._data(self._get("BankAccount/GetCountries"))

    def get_valid_bank_accounts_for_delete_and_set_new_default(self) -> dict:
        return self._data(self._get("BankAccount/GetValidBankAccountsForDeleteAndSetNewDefault"))

    def insert_domestic_bank_account(self, data: dict) -> dict:
        return self._data(self._post("BankAccount/InsertDomesticBankAccountItem", data=data))

    def insert_foreign_bank_account(self, data: dict) -> dict:
        return self._data(self._post("BankAccount/InsertForeignBankAccountItem", data=data))

    def modify_bank_account(self, data: dict) -> dict:
        return self._data(self._post("BankAccount/ModifyBankAccountItem", data=data))

    def delete_bank_account(self, account_id: str) -> dict:
        return self._data(self._post("BankAccount/DeleteBankAccountItem", data={"id": account_id}))

    def delete_and_set_new_default_bank_account(self, data: dict) -> dict:
        return self._data(self._post("BankAccount/DeleteAndSetNewDefaultBankAccount", data=data))

    def bank_account_otp_statement(self) -> dict:
        return self._data(self._get("BankAccount/BankAccountOtpStatement"))

    def change_bank_account_otp_statement(self, data: dict) -> dict:
        return self._data(self._post("BankAccount/ChangeBankAccountOtpStatement", data=data))

    # ===================================================================
    # PAYING ORGANIZATION PARTNERS (11 endpoints)
    # ===================================================================

    def get_paying_organization_partners(self) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetPayingOrganizationPartners"))

    def get_paying_organization_partner_detail(self, partner_id: str) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetPayingOrganizationPartnerDetail", params={"id": partner_id}))

    def get_paying_organization_partner_data(self, partner_id: str) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetPayingOrganizationPartnerData", params={"id": partner_id}))

    def get_exterior_organizations(self) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetExteriorOrganizations"))

    def get_boss_exterior_organization_list(self) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetBossExteriorOrganizationList"))

    def get_exterior_org_category_for_insert(self) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetExteriorOrganizationCategoryForInsertPayingOrganizationPartner"))

    def get_payer_type_for_insert(self) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetPayerTypeForInsertPayingOrganizationPartner"))

    def get_nav_exterior_org_by_tax_number(self, tax_number: str) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetNavExteriorOrganizationDataByTaxNumber", params={"taxNumber": tax_number}))

    def get_paying_orgs_for_assignment(self) -> dict:
        return self._data(self._get("PayingOrganizationPartners/GetPayingOrganizationsForAssignmentItemToBePayed"))

    def insert_paying_organization_partner(self, data: dict) -> dict:
        return self._data(self._post("PayingOrganizationPartners/InsertPayingOrganizationPartner", data=data))

    def delete_paying_organization_partner(self, partner_id: str) -> dict:
        return self._data(self._post("PayingOrganizationPartners/DeletePayingOrganizationPartner", data={"id": partner_id}))

    # ===================================================================
    # PAYING PARTNERS (5 endpoints)
    # ===================================================================

    def get_paying_partner_countries(self) -> dict:
        return self._data(self._get("PayingPartners/GetCountries"))

    def get_paying_partner_cities(self, query: str) -> dict:
        return self._data(self._get("PayingPartners/GetCitiesForPayingPartnersAutocomplete", params={"query": query}))

    def insert_paying_partner(self, data: dict) -> dict:
        return self._data(self._post("PayingPartners/InsertPayingPartnerForItemToBePayed", data=data))

    def modify_paying_partner(self, data: dict) -> dict:
        return self._data(self._post("PayingPartners/ModifyPayingPartnerForItemToBePayed", data=data))

    def delete_paying_partner(self, partner_id: str) -> dict:
        return self._data(self._post("PayingPartners/DeletePayingPartnerFromItemToBePayed", data={"id": partner_id}))

    # ===================================================================
    # PAYING PRIVATE PERSON PARTNERS (7 endpoints)
    # ===================================================================

    def get_paying_private_person_partners(self) -> dict:
        return self._data(self._get("PayingPrivatePersonPartners/GetPayingPrivatePersonPartners"))

    def get_paying_private_person_partner_detail(self, partner_id: str) -> dict:
        return self._data(self._get("PayingPrivatePersonPartners/GetPayingPrivatePersonPartnerDetail", params={"id": partner_id}))

    def get_paying_private_partner_data(self, partner_id: str) -> dict:
        return self._data(self._get("PayingPrivatePersonPartners/GetPayingPrivatePartnerData", params={"id": partner_id}))

    def get_paying_private_partners_for_assignment(self) -> dict:
        return self._data(self._get("PayingPrivatePersonPartners/GetPayingPrivatePartnersForAssignmentToItemToBePayed"))

    def insert_paying_private_person_partner(self, data: dict) -> dict:
        return self._data(self._post("PayingPrivatePersonPartners/InsertPayingPrivatePersonPartner", data=data))

    def modify_paying_private_person_partner(self, data: dict) -> dict:
        return self._data(self._post("PayingPrivatePersonPartners/ModifyPayingPrivatePersonPartner", data=data))

    def delete_paying_private_person_partner(self, partner_id: str) -> dict:
        return self._data(self._post("PayingPrivatePersonPartners/DeletePayingPrivatePersonPartner", data={"id": partner_id}))

    # ===================================================================
    # SCHOLARSHIP (2 endpoints)
    # ===================================================================

    def get_scholarship_payment_terms(self) -> dict:
        return self._data(self._get("Scholarship/GetScholarshipAvailablePaymentTerms"))

    def get_scholarship_payments(self, term_id: str | None = None) -> dict:
        params = {"termId": term_id} if term_id else {}
        return self._data(self._get("Scholarship/GetScholarshipPayments", params=params))

    # ===================================================================
    # STUDENT LOAN (2 endpoints)
    # ===================================================================

    def get_student_loan_info(self) -> dict:
        return self._data(self._get("StudentLoan/GetStudentLoan"))

    def student_loan_postulation(self, data: dict) -> dict:
        return self._data(self._post("StudentLoan/StudentLoanPostulation", data=data))

    # ===================================================================
    # STUDENT LOAN PAY (4 endpoints)
    # ===================================================================

    def is_student_loan(self) -> dict:
        return self._data(self._get("StudentLoanPay/IsStudentLoan"))

    def pay_imposition_by_student_loan(self, data: dict) -> dict:
        return self._data(self._post("StudentLoanPay/PayImpositionByStudentLoan", data=data))

    def delete_student_loan_pay(self, data: dict) -> dict:
        return self._data(self._post("StudentLoanPay/DeleteStudentLoan", data=data))

    def validate_delete_student_loan(self, data: dict) -> dict:
        return self._data(self._post("StudentLoanPay/ValidateDeleteStudentLoan", data=data))

    # ===================================================================
    # PERSONAL DATA (113 endpoints)
    # ===================================================================

    def get_general_user_data(self) -> dict:
        return self._data(self._get("PersonalData/GetGeneralUserData"))

    def get_general_user_data_for_modify(self) -> dict:
        return self._data(self._get("PersonalData/GetGeneralUserDataForModify"))

    def modify_general_user_data(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyGeneralUserData", data=data))

    def get_student_personal_data_contacts(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentPersonalDataContacts"))

    def get_personal_data_terms(self) -> dict:
        return self._data(self._get("PersonalData/GetTerms"))

    def get_personal_data_terms_by_training(self, training_id: str) -> dict:
        return self._data(self._get("PersonalData/GetTermsByTrainingId", params={"studentTrainingId": training_id}))

    def get_personal_data_countries(self) -> dict:
        return self._data(self._get("PersonalData/GetCountries"))

    # Addresses
    def get_student_address_details(self, address_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentAddressDetails", params={"id": address_id}))

    def get_student_address_for_modify_type(self, address_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentAddressForModifyAddressType", params={"id": address_id}))

    def get_address_breakdown_format(self) -> dict:
        return self._data(self._get("PersonalData/GetAddressBreakdownFormat"))

    def get_address_type(self) -> dict:
        return self._data(self._get("PersonalData/GetAddressType"))

    def get_address_type_for_modify(self) -> dict:
        return self._data(self._get("PersonalData/GetAddressTypeForModify"))

    def get_address_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetAddressDocumentationTypes"))

    def get_cities_for_address(self, query: str) -> dict:
        return self._data(self._get("PersonalData/GetCitiesForStudentAddressAutocomplete", params={"query": query}))

    def insert_student_address(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertStudentAddressByAddressType", data=data))

    def modify_student_address(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentAddressByAddressType", data=data))

    def delete_student_address(self, address_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentAddress", data={"id": address_id}))

    def retrieve_city_name_suggestions(self, query: str) -> dict:
        return self._data(self._get("PersonalData/RetrieveCityNameSuggestionsForAddress", params={"query": query}))

    def retrieve_postal_code_suggestions(self, query: str) -> dict:
        return self._data(self._get("PersonalData/RetrievePostalCodeSuggestionsForAddress", params={"query": query}))

    # Emails
    def get_student_email_details(self, email_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentEmailDetails", params={"id": email_id}))

    def get_student_email_modify_data(self, email_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentEmailModifyData", params={"id": email_id}))

    def get_email_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetEmailDocumentationTypes"))

    def get_checkbox_state_for_new_email(self) -> dict:
        return self._data(self._get("PersonalData/GetCheckBoxStateForNewEmail"))

    def insert_student_email(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertStudentEmailItem", data=data))

    def modify_student_email(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentEmailItem", data=data))

    def delete_student_email(self, email_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentEmailItem", data={"id": email_id}))

    # Phone numbers
    def get_student_phone_details(self, phone_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentPhoneNumberDetails", params={"id": phone_id}))

    def get_student_phone_modify_data(self, phone_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentPhoneNumberModifyData", params={"id": phone_id}))

    def get_telephone_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetTelephoneDocumentationTypes"))

    def get_telephone_type(self) -> dict:
        return self._data(self._get("PersonalData/GetTelephoneType"))

    def insert_student_phone(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertStudentPhoneNumberItem", data=data))

    def modify_student_phone(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentPhoneNumberItem", data=data))

    def delete_student_phone(self, phone_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentPhoneNumberItem", data={"id": phone_id}))

    # Web addresses
    def get_student_web_address_details(self, web_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentWebAddressDetails", params={"id": web_id}))

    def get_student_web_address_modify_data(self, web_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentWebAddressModifyData", params={"id": web_id}))

    def get_web_address_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetWebAddressDocumentationTypes"))

    def insert_student_web_address(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertWebAddressItem", data=data))

    def modify_student_web_address(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyWebAddressItem", data=data))

    def delete_student_web_address(self, web_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentWebAddressItem", data={"id": web_id}))

    # ICE Users (emergency contacts)
    def get_ice_user_details(self, ice_id: str) -> dict:
        return self._data(self._get("PersonalData/GetIceUserDetails", params={"id": ice_id}))

    def get_ice_user_modify_data(self, ice_id: str) -> dict:
        return self._data(self._get("PersonalData/GetIceUserModifyData", params={"id": ice_id}))

    def get_ice_user_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetIceUserDocumentationTypes"))

    def insert_ice_user(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertIceUserDetails", data=data))

    def modify_ice_user(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyIceUserDetails", data=data))

    def delete_ice_user(self, ice_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteIceUser", data={"id": ice_id}))

    # Language exams
    def get_student_language_exams(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentLanguageExam"))

    def get_student_language_exam_details(self, exam_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentLanguageExamDetails", params={"id": exam_id}))

    def get_student_language_exam_modify_data(self, exam_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentLanguageExamModifyData", params={"id": exam_id}))

    def get_language_exam_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetLanguageExamDocumentationTypes"))

    def insert_student_language_exam(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertStudentLanguageExam", data=data))

    def modify_student_language_exam(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentLanguageExam", data=data))

    def delete_student_language_exam(self, exam_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentLanguageExam", data={"id": exam_id}))

    # Personal documents
    def get_student_personal_documents(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentPersonalDocuments"))

    def get_student_personal_document_details(self, doc_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentPersonalDocumentDetails", params={"id": doc_id}))

    def get_student_personal_document_modify_data(self, doc_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentPersonalDocumentModifyData", params={"id": doc_id}))

    def get_personal_document_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetPersonalDocumentDocumentationTypes"))

    def insert_student_personal_document(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertPersonalDocument", data=data))

    def modify_student_personal_document(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyPersonalDocument", data=data))

    def delete_student_personal_document(self, doc_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentPersonalDocument", data={"id": doc_id}))

    # Competitions
    def get_student_competitions(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentCompetitions"))

    def get_student_competition_details(self, comp_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentCompetitionDetails", params={"id": comp_id}))

    def get_student_competition_modify_data(self, comp_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentCompetitionModifyData", params={"id": comp_id}))

    def get_competition_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetCompetitionDocumentationTypes"))

    def get_trainings_for_competition(self) -> dict:
        return self._data(self._get("PersonalData/GetTrainingsForCompetition"))

    def insert_student_competition(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertStudentCompetition", data=data))

    def modify_student_competition(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentCompetition", data=data))

    def delete_student_competition(self, comp_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentCompetition", data={"id": comp_id}))

    # Pre-qualifications
    def get_student_pre_qualifications(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentPreQualifications"))

    def get_student_pre_qualification_details(self, qual_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentPreQualificationDetails", params={"id": qual_id}))

    def get_student_pre_qualification_modify_data(self, qual_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentPreQualificationModifyData", params={"id": qual_id}))

    def get_pre_qualification_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetPreQualificationDocumentationTypes"))

    def insert_student_pre_qualification(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertStudentPreQualification", data=data))

    def modify_student_pre_qualification(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentPreQualification", data=data))

    def delete_student_pre_qualification(self, qual_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentPreQualification", data={"id": qual_id}))

    # Preferential treatments
    def get_student_preferential_treatments(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentPreferentialTreatmentsData"))

    def get_student_preferential_treatment(self, treatment_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentPreferentialTreatmentData", params={"id": treatment_id}))

    def get_student_preferential_treatment_modify_data(self, treatment_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentPreferentialTreatmentModifyData", params={"id": treatment_id}))

    def get_preferential_treatment_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentPreferentialTreatmentDocumentationTypes"))

    def get_category_for_preferential_treatment(self) -> dict:
        return self._data(self._get("PersonalData/GetCategoryForPreferentialTreatment"))

    def insert_student_preferential_treatment(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertStudentPreferentialTreatment", data=data))

    def modify_student_preferential_treatment(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentPreferentialTreatment", data=data))

    def delete_student_preferential_treatment(self, treatment_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentPreferentialTreatment", data={"id": treatment_id}))

    # Parallel trainings
    def get_student_parallel_trainings(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentParallelTrainings"))

    def get_student_parallel_training_details(self, training_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentParallelTrainingsDetails", params={"id": training_id}))

    def get_student_parallel_training_modify_data(self, training_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentParallelTrainingsModifyData", params={"id": training_id}))

    def get_parallel_training_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentParallelTrainingDocumentationTypes"))

    def insert_student_parallel_training(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertStudentParallelTraining", data=data))

    def modify_student_parallel_training(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentParallelTraining", data=data))

    def delete_student_parallel_training(self, training_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentParallelTraining", data={"id": training_id}))

    # Guest trainings
    def get_student_guest_trainings(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentGuestTrainings"))

    def get_student_guest_training_details(self, training_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentGuestTrainingsDetails", params={"id": training_id}))

    def get_student_guest_training_modify_data(self, training_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentGuestTrainingsModifyData", params={"id": training_id}))

    def get_guest_training_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetGuestStudentTrainingDocumentationTypes"))

    def insert_student_guest_training(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertGuestStudentTraining", data=data))

    def modify_student_guest_training(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyStudentGuestTraining", data=data))

    def delete_student_guest_training(self, training_id: str) -> dict:
        return self._data(self._post("PersonalData/DeleteStudentGuestTraining", data={"id": training_id}))

    # Student card
    def get_student_card_details_personal(self, card_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentCardDetails", params={"id": card_id}))

    def get_student_card_sticker_details(self, card_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentCardStickerDetails", params={"id": card_id}))

    # Statements
    def get_student_statements(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentStatements"))

    def get_student_statement_detail(self, statement_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentStatementDetail", params={"id": statement_id}))

    def get_statement_documentation_types(self) -> dict:
        return self._data(self._get("PersonalData/GetStatementDocumentationTypes"))

    def insert_document_and_statement(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/InsertDocumentumAndDeniedOrAcceptedStatement", data=data))

    def modify_document_and_statement(self, data: dict) -> dict:
        return self._data(self._post("PersonalData/ModifyDocumentumAndStatement", data=data))

    # GDPR statements
    def get_student_gdpr_statements(self) -> dict:
        return self._data(self._get("PersonalData/GetStudentGdprStatements"))

    def get_student_gdpr_statement_details(self, statement_id: str) -> dict:
        return self._data(self._get("PersonalData/GetStudentGdprStatementDetails", params={"id": statement_id}))

    def get_gdpr_statement_file(self, statement_id: str) -> dict:
        return self._data(self._get("PersonalData/GetGdprStatementFile", params={"id": statement_id}))

    # Data modification history
    def get_data_modification_history(self, params: dict | None = None) -> dict:
        return self._data(self._get("PersonalData/GetDataModificationHistory", params=params))

    def get_data_modification_history_details(self, history_id: str) -> dict:
        return self._data(self._get("PersonalData/GetDataModificationHistoryDetails", params={"id": history_id}))

    def get_data_modification_history_detail_changes(self, history_id: str) -> dict:
        return self._data(self._get("PersonalData/GetDataModificationHistoryDetailChanges", params={"id": history_id}))

    def get_data_modification_history_table_names(self) -> dict:
        return self._data(self._get("PersonalData/GetDataModificationHistoryTableNames"))

    # Other personal data
    def get_exterior_org_data_query(self, query: str) -> dict:
        return self._data(self._get("PersonalData/GetExteriorOrganizationDataQuery", params={"query": query}))

    def get_sub_type_for_type(self, type_id: str) -> dict:
        return self._data(self._get("PersonalData/GetSubTypeForType", params={"typeId": type_id}))

    # ===================================================================
    # STUDENT CARD (12 endpoints)
    # ===================================================================

    def get_nek_data_sheet_param(self) -> dict:
        return self._data(self._get("StudentCard/GetNEKDataSheetSystemParameterValue"))

    def get_student_card_claim_with_document_param(self) -> dict:
        return self._data(self._get("StudentCard/GetStudentCardClaimWithDocumentSystemParameterValue"))

    def get_student_card_claim(self) -> dict:
        return self._data(self._get("StudentCard/GetStudentCardClaim"))

    def get_secondary_institute(self) -> dict:
        return self._data(self._get("StudentCard/GetSecondaryInstitute"))

    def get_student_card_address(self) -> dict:
        return self._data(self._get("StudentCard/GetStudentAddress"))

    def get_student_card_current_address(self) -> dict:
        return self._data(self._get("StudentCard/GetStudentCardCurrentAddress"))

    def get_student_card_previous_claims(self) -> dict:
        return self._data(self._get("StudentCard/GetStudentCardPreviousClaims"))

    def get_student_card_previous_claim_details(self, claim_id: str) -> dict:
        return self._data(self._get("StudentCard/GetStudentCardPreviousClaimDetails", params={"id": claim_id}))

    def insert_student_card_claim(self, data: dict) -> dict:
        return self._data(self._post("StudentCard/InsertStudentCardClaim", data=data))

    def modify_student_card_claim(self, data: dict) -> dict:
        return self._data(self._post("StudentCard/ModifyStudentCardClaim", data=data))

    def delete_student_card_claim(self, claim_id: str) -> dict:
        return self._data(self._post("StudentCard/DeleteStudentCardClaim", data={"id": claim_id}))

    def student_card_claim_process(self, data: dict) -> dict:
        return self._data(self._post("StudentCard/StudentCardClaimProcess", data=data))

    # ===================================================================
    # PERIODS (3 endpoints)
    # ===================================================================

    def get_period_terms(self) -> dict:
        return self._data(self._get("Periods/GetTerms"))

    def get_periods(self, term_id: str) -> dict:
        return self._data(self._get("Periods/GetPeriods", params={"termId": term_id}))

    def get_period_data(self, period_id: str) -> dict:
        return self._data(self._get("Periods/GetPeriodData", params={"id": period_id}))

    # ===================================================================
    # TASKS (28 endpoints)
    # ===================================================================

    def get_tasks_terms(self) -> dict:
        return self._data(self._get("Tasks/GetTerms"))

    def get_actual_tasks(self, params: dict | None = None) -> dict:
        return self._data(self._get("Tasks/GetActualTasksList", params=params))

    def get_future_tasks(self, params: dict | None = None) -> dict:
        return self._data(self._get("Tasks/GetFutureTasksList", params=params))

    def get_previous_tasks(self, params: dict | None = None) -> dict:
        return self._data(self._get("Tasks/GetPreviusTasksList", params=params))

    def get_new_signin_tasks(self, params: dict | None = None) -> dict:
        return self._data(self._get("Tasks/GetNewSignInTasksList", params=params))

    def get_task_detail(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetTaskDetail", params={"id": task_id}))

    def get_subtasks(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetSubtasks", params={"taskId": task_id}))

    def get_task_supplements(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetSupplements", params={"taskId": task_id}))

    def get_task_rooms_list(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetRoomsList", params={"taskId": task_id}))

    def get_task_room_detail(self, room_id: str) -> dict:
        return self._data(self._get("Tasks/GetRoomDetail", params={"roomId": room_id}))

    def get_midterm_task_results(self, params: dict | None = None) -> dict:
        return self._data(self._get("Tasks/GetMidTermTaskResults", params=params))

    def get_dashboard_tasks_data(self) -> dict:
        return self._data(self._get("Tasks/GetDashboardTasksData"))

    def get_dashboard_expiring_tasks(self) -> dict:
        return self._data(self._get("Tasks/GetDashboardExpiringTasksData"))

    def get_task_documentations_list(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetDocumentationsList", params={"taskId": task_id}))

    def get_task_documentation_detail(self, doc_id: str) -> dict:
        return self._data(self._get("Tasks/GetDocumentationsDetail", params={"id": doc_id}))

    def get_task_documentations_type_id(self) -> dict:
        return self._data(self._get("Tasks/GetDocumentationsTypeId"))

    def get_submitted_task_documentations(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetSubmittedDocumentationsList", params={"taskId": task_id}))

    def get_submitted_task_document_detail(self, doc_id: str) -> dict:
        return self._data(self._get("Tasks/GetSubmittedDocumentDetail", params={"id": doc_id}))

    def subscribe_task(self, data: dict) -> dict:
        return self._data(self._post("Tasks/SubscribeTask", data=data))

    def unsubscribe_task(self, data: dict) -> dict:
        return self._data(self._post("Tasks/UnsubscribeTask", data=data))

    def add_documentations_to_task(self, data: dict) -> dict:
        return self._data(self._post("Tasks/AddDocumentationsToDocument", data=data))

    def delete_task_documentation(self, doc_id: str) -> dict:
        return self._data(self._post("Tasks/DeleteTaskDocumentation", data={"id": doc_id}))

    def upload_files_for_task(self, data: dict) -> dict:
        return self._data(self._post("Tasks/UploadFilesForTask", data=data))

    def download_task_documentation(self, params: dict) -> dict:
        return self._data(self._get("Tasks/DownloadDocumentationOrZip", params=params))

    def download_selected_task_documentations(self, params: dict) -> dict:
        return self._data(self._get("Tasks/DownloadSelectedDocumentationsFromSubmittedDocument", params=params))

    def get_unipoll_survey_list_for_task(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetUnipollSurveyListForTask", params={"taskId": task_id}))

    def get_unipoll_survey_list_for_task_practice(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetUnipollSurveyListForTaskPractice", params={"taskId": task_id}))

    def get_unipoll_task_uri(self, task_id: str) -> dict:
        return self._data(self._get("Tasks/GetUnipollTaskUriStudent", params={"taskId": task_id}))

    # ===================================================================
    # CONSULTATION (12 endpoints)
    # ===================================================================

    def get_consultation_terms(self) -> dict:
        return self._data(self._get("Consultation/GetTerms"))

    def get_consultations(self, params: dict | None = None) -> dict:
        return self._data(self._get("Consultation/GetConsultations", params=params))

    def get_consultation_details(self, consultation_id: str) -> dict:
        return self._data(self._get("Consultation/GetConsultationDetails", params={"id": consultation_id}))

    def get_consultation_appointments(self, consultation_id: str) -> dict:
        return self._data(self._get("Consultation/GetConsultationAppointments", params={"consultationId": consultation_id}))

    def get_consultation_appointment_details(self, appointment_id: str) -> dict:
        return self._data(self._get("Consultation/GetConsultationAppointmentDetails", params={"id": appointment_id}))

    def get_students_applied_for_consultation(self, appointment_id: str) -> dict:
        return self._data(self._get("Consultation/GetStudentsAppliedForConsultationAppointment", params={"id": appointment_id}))

    def get_student_details_for_consultation(self, appointment_id: str) -> dict:
        return self._data(self._get("Consultation/GetStudentDetailsAppliedForConsultationAppointment", params={"id": appointment_id}))

    def get_reserved_rooms_for_consultation(self, appointment_id: str) -> dict:
        return self._data(self._get("Consultation/GetReservedRoomsForConsultationAppointment", params={"id": appointment_id}))

    def get_reserved_room_details_for_consultation(self, room_id: str) -> dict:
        return self._data(self._get("Consultation/GetReservedRoomDetailsForConsultationAppointment", params={"roomId": room_id}))

    def apply_all_consultation_appointments(self, data: dict) -> dict:
        return self._data(self._post("Consultation/ApplyAllConsultationAppointments", data=data))

    def drop_all_applied_consultation_appointments(self, data: dict) -> dict:
        return self._data(self._post("Consultation/DropAllAppliedConsultationAppointments", data=data))

    def overwrite_applied_consultation_appointments(self, data: dict) -> dict:
        return self._data(self._post("Consultation/OverwriteExistingAppliedConsultationAppointments", data=data))

    # ===================================================================
    # QUESTIONNAIRES (17 endpoints)
    # ===================================================================

    def get_omhv_report_url(self) -> str:
        return self._data(self._get("Questionnaires/GetOMHVReportURLForView"))

    def get_questionnaires(self, params: dict | None = None) -> dict:
        return self._data(self._get("Questionnaires/GetQuestionnaires", params=params))

    def get_questionnaire_details(self, questionnaire_id: str) -> dict:
        return self._data(self._get("Questionnaires/GetQuestionnaireDetailsData", params={"id": questionnaire_id}))

    def get_questionnaire_fill_out_states(self) -> dict:
        return self._data(self._get("Questionnaires/GetQuestionnaireFillOutStates"))

    def get_finished_questionnaires(self, params: dict | None = None) -> dict:
        return self._data(self._get("Questionnaires/GetFinishedQuestionnaires", params=params))

    def get_finished_questionnaire_details(self, questionnaire_id: str) -> dict:
        return self._data(self._get("Questionnaires/GetFinishedQuestionnaireDetailsData", params={"id": questionnaire_id}))

    def get_omhv_reports(self, params: dict | None = None) -> dict:
        return self._data(self._get("Questionnaires/GetOMHVReports", params=params))

    def get_omhv_report_details(self, report_id: str) -> dict:
        return self._data(self._get("Questionnaires/GetOMHVReportDetailsData", params={"id": report_id}))

    def get_omhv_reports_terms(self) -> dict:
        return self._data(self._get("Questionnaires/GetTermsForOMHVReports"))

    def get_questionnaire_student_terms(self) -> dict:
        return self._data(self._get("Questionnaires/GetStudentTerms"))

    def get_unipoll_reports(self, params: dict | None = None) -> dict:
        return self._data(self._get("Questionnaires/GetUnipollReports", params=params))

    def get_unipoll_report_details(self, report_id: str) -> dict:
        return self._data(self._get("Questionnaires/GetUnipollReportDetailsData", params={"id": report_id}))

    def get_unipoll_url_for_finished_questionnaire(self, questionnaire_id: str) -> dict:
        return self._data(self._get("Questionnaires/GetUnipollURLForFinishedQuestionnaireForView", params={"id": questionnaire_id}))

    def get_unipoll_url_for_report(self, report_id: str) -> dict:
        return self._data(self._get("Questionnaires/GetUnipollURLForUnipollReportForView", params={"id": report_id}))

    def get_unipoll_url_with_token_for_fill(self, unipoll_report_id: str) -> dict:
        return self._data(self._get("Questionnaires/GetUnipollURLWithTokenForFill", params={"unipollReportId": unipoll_report_id}))

    def is_unipoll_report_url_empty(self) -> dict:
        return self._data(self._get("Questionnaires/IsUnipollReportUrlEmpty"))

    def is_unipoll_url_empty(self) -> dict:
        return self._data(self._get("Questionnaires/IsUnipollUrlEmpty"))

    # ===================================================================
    # OFFERED GRADES (3 endpoints)
    # ===================================================================

    def get_offered_grades(self) -> dict:
        return self._data(self._get("OfferedGrades/GetOfferedGrades"))

    def get_offered_grade_details(self, grade_id: str) -> dict:
        return self._data(self._get("OfferedGrades/GetOfferedGradeDetails", params={"id": grade_id}))

    def accept_or_reject_offered_grade(self, data: dict) -> dict:
        return self._data(self._post("OfferedGrades/AcceptOrRejectOfferedGrade", data=data))

    # ===================================================================
    # CONTEXT USER PROFILE (22 endpoints)
    # ===================================================================

    def get_calendar_selected_view(self) -> dict:
        return self._data(self._get("ContextUserProfile/GetCalendarSelectedView"))

    def save_calendar_selected_view(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveCalendarSelectedView", data=data))

    def get_calendar_selected_types(self) -> dict:
        return self._data(self._get("ContextUserProfile/GetCalendarSelectedTypes"))

    def save_calendar_selected_types(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveCalendarSelectedTypes", data=data))

    def get_subject_signin_selected_view(self) -> dict:
        return self._data(self._get("ContextUserProfile/GetSubjectSigninSelectedView"))

    def save_subject_signin_selected_view(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveSubjectSigninSelectedView", data=data))

    def get_subject_signin_warning_modal_states(self) -> dict:
        return self._data(self._get("ContextUserProfile/GetSubjectSigninWarningModalsStates"))

    def save_subject_signin_warning_modal_states(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveSubjectSigninWarningModalsStates", data=data))

    def get_column_order(self, params: dict) -> dict:
        return self._data(self._get("ContextUserProfile/GetColumnOrder", params=params))

    def save_column_order(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveColumnOrder", data=data))

    def get_column_order_type(self) -> dict:
        return self._data(self._get("ContextUserProfile/GetColumnOrderType"))

    def save_column_order_type(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveColumnOrderType", data=data))

    def get_dashboard_sort_item(self) -> dict:
        return self._data(self._get("ContextUserProfile/GetDashboardSortItem"))

    def save_dashboard_sort_item(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveDashboardSortItem", data=data))

    def save_dashboard_open_close(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveDashboardOpenClose", data=data))

    def get_filter(self, params: dict) -> dict:
        return self._data(self._get("ContextUserProfile/GetFilter", params=params))

    def save_filter(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveFilter", data=data))

    def delete_filter(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/DeleteFilter", data=data))

    def save_favourite_menu(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveFavouriteMenu", data=data))

    def get_onboarding_profile_data(self) -> dict:
        return self._data(self._get("ContextUserProfile/GetOnboardingProfileData"))

    def save_onboarding_profile_data(self, data: dict) -> dict:
        return self._data(self._post("ContextUserProfile/SaveOnboardingProfileData", data=data))

    def reset_context_user_profile(self) -> dict:
        return self._data(self._post("ContextUserProfile/ResetContextUserProfile"))

    # ===================================================================
    # PROFILES (1 endpoint)
    # ===================================================================

    def get_favourites(self) -> list:
        return self._data(self._get("Profiles/Favourites"))

    # ===================================================================
    # USER PROFILE (6 endpoints)
    # ===================================================================

    def get_user_profile_settings(self) -> dict:
        return self._data(self._get("UserProfile/GetUserProfileSettings"))

    def save_user_profile_settings(self, data: dict) -> dict:
        return self._data(self._post("UserProfile/SaveUserProfileSettings", data=data))

    def get_user_profile_default_avatars(self) -> dict:
        return self._data(self._get("UserProfile/GetDefaultAvatars"))

    def get_user_profile_fallback_colors(self) -> dict:
        return self._data(self._get("UserProfile/GetDefaultFallbackProfilePictureColorCodes"))

    def get_user_profile_users_avatar(self, user_ids: list[str]) -> dict:
        params = {}
        for i, uid in enumerate(user_ids):
            params[f"userIds[{i}]"] = uid
        return self._data(self._get("UserProfile/GetUsersAvatar", params=params))

    def is_password_modification_allowed(self) -> dict:
        return self._data(self._get("UserProfile/IsPasswordModificationAllowed"))

    # ===================================================================
    # USER SEARCH (11 endpoints)
    # ===================================================================

    def get_users(self, params: dict) -> dict:
        return self._data(self._get("UserSearch/GetUsers", params=params))

    def get_user_data(self, user_id: str) -> dict:
        return self._data(self._get("UserSearch/GetUserData", params={"userId": user_id}))

    def get_message_recipient_users(self, params: dict) -> dict:
        return self._data(self._get("UserSearch/GetMessageRecipientUsers", params=params))

    def get_person_group_users(self, params: dict) -> dict:
        return self._data(self._get("UserSearch/GetPersonGroupUsers", params=params))

    def get_interior_organization_types(self) -> dict:
        return self._data(self._get("UserSearch/GetInteriorOrganizationTypes"))

    def get_student_modules(self, params: dict | None = None) -> dict:
        return self._data(self._get("UserSearch/GetStudentModules", params=params))

    def get_student_module_terms(self) -> dict:
        return self._data(self._get("UserSearch/GetStudentModuleTerms"))

    def get_student_module_types(self) -> dict:
        return self._data(self._get("UserSearch/GetStudentModuleTypes"))

    def get_student_training_sites(self) -> dict:
        return self._data(self._get("UserSearch/GetStudentTrainingSites"))

    def get_erasmus_practice_coordinators(self, params: dict) -> dict:
        return self._data(self._get("UserSearch/GetGeneralUserSearchForTheErasmusPracticeCoordinators", params=params))

    # ===================================================================
    # PERSON GROUP (7 endpoints)
    # ===================================================================

    def get_own_person_groups(self) -> dict:
        return self._data(self._get("PersonGroup/GetOwnPersonGroups"))

    def create_person_group(self, data: dict) -> dict:
        return self._data(self._post("PersonGroup/CreatePersonGroup", data=data))

    def update_person_group(self, data: dict) -> dict:
        return self._data(self._post("PersonGroup/UpdatePersonGroup", data=data))

    def delete_person_group(self, group_id: str) -> dict:
        return self._data(self._post("PersonGroup/DeletePersonGroup", data={"id": group_id}))

    def add_person_group_members(self, data: dict) -> dict:
        return self._data(self._post("PersonGroup/AddPersonGroupMembers", data=data))

    def remove_person_group_member(self, data: dict) -> dict:
        return self._data(self._post("PersonGroup/RemovePersonGroupMember", data=data))

    def save_person_group_member_note(self, data: dict) -> dict:
        return self._data(self._post("PersonGroup/SavePersonGroupMemberNote", data=data))

    # ===================================================================
    # DOCUMENT CONTAINER (49 endpoints)
    # ===================================================================

    def get_document_container_dashboard(self) -> dict:
        return self._data(self._get("DocumentContainer/GetDashboardData"))

    def get_documents_uploaded_by_student(self, params: dict | None = None) -> dict:
        return self._data(self._get("DocumentContainer/GetDocumentsUploadedByStudent", params=params))

    def get_documents_uploaded_by_student_types(self) -> dict:
        return self._data(self._get("DocumentContainer/GetDocumentsUploadedByStudentTypes"))

    def get_document_uploaded_by_student_details(self, doc_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetDocumentUploadedByStudentDetails", params={"id": doc_id}))

    def get_documents_uploaded_for_student(self, params: dict | None = None) -> dict:
        return self._data(self._get("DocumentContainer/GetDocumentsUploadedForStudent", params=params))

    def get_documents_uploaded_for_student_types(self) -> dict:
        return self._data(self._get("DocumentContainer/GetDocumentUploadedForStudentTypes"))

    def get_document_details_uploaded_for_student(self, doc_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetDocumentDetailsUploadedForStudent", params={"id": doc_id}))

    def get_document_container_student_terms(self) -> dict:
        return self._data(self._get("DocumentContainer/GetStudentTerms"))

    def get_document_type_id(self) -> dict:
        return self._data(self._get("DocumentContainer/GetDocumentTypeId"))

    def get_nms_documentation_type_id(self) -> dict:
        return self._data(self._get("DocumentContainer/GetNMSDocumentationTypId"))

    def get_container_status(self, container_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetContainerStatus", params={"id": container_id}))

    def save_files_to_container(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/SaveFilesToContainer", data=data))

    def save_file_details(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/SaveFileDetails", data=data))

    def delete_containers(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/DeleteContainers", data=data))

    def delete_files_from_document_container(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/DeleteFilesFromDocumentContainer", data=data))

    def download_documents(self, params: dict) -> dict:
        return self._data(self._get("DocumentContainer/DownloadDocuments", params=params))

    def download_documentation_or_zip(self, params: dict) -> dict:
        return self._data(self._get("DocumentContainer/DownloadDocumentationOrZip", params=params))

    # Shareable folders
    def get_shareable_folders(self) -> dict:
        return self._data(self._get("DocumentContainer/GetShareableFolders"))

    def get_shareable_folder_details(self, folder_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetShareableFolderDetails", params={"id": folder_id}))

    def get_shareable_folder_files(self, folder_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetShareableFolderDetailsFiles", params={"id": folder_id}))

    def get_shareable_folder_document_details(self, doc_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetShareableFolderDocumentDetails", params={"id": doc_id}))

    def modify_folder_base_details(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/ModifyFolderBaseDetails", data=data))

    def upload_documentations_to_folder(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/UploadDocumentationsToFolder", data=data))

    def delete_files_from_folder(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/DeleteFilesFromFolder", data=data))

    # Folder shared with student
    def get_folders_shared_with_student(self) -> dict:
        return self._data(self._get("DocumentContainer/GetFoldersSharedWithStudent"))

    def get_folders_shared_with_student_share_types(self) -> dict:
        return self._data(self._get("DocumentContainer/GetFoldersSharedWithStudentShareTypes"))

    def get_folder_shared_with_student_details(self, folder_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetFolderSharedWithStudentDetails", params={"id": folder_id}))

    def get_folder_shared_with_student_files(self, folder_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetFolderSharedWithStudentDetailsFiles", params={"id": folder_id}))

    def get_folder_shared_with_student_doc_details(self, doc_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetFolderSharedWithStudentDocumentDetails", params={"id": doc_id}))

    # Folder connections
    def get_folder_connections(self, folder_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetFolderConnections", params={"folderId": folder_id}))

    def get_folder_person_group_connections(self, folder_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetFolderPersonGroupConnections", params={"folderId": folder_id}))

    def get_folder_user_connections(self, folder_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetFolderUserConnections", params={"folderId": folder_id}))

    def get_folder_virtual_space_connections(self, folder_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetFolderVirtualSpaceConnections", params={"folderId": folder_id}))

    def get_linkable_person_groups(self) -> dict:
        return self._data(self._get("DocumentContainer/GetLinkablePersonGroups"))

    def get_linkable_virtual_spaces(self) -> dict:
        return self._data(self._get("DocumentContainer/GetLinkableVirtualSpaces"))

    def link_person_group_to_folder(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/LinkPersonGroup", data=data))

    def link_user_to_folder(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/LinkUser", data=data))

    def link_virtual_space_to_folder(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/LinkVirtualSpace", data=data))

    def remove_person_group_from_folder(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/RemovePersonGroupFromFolder", data=data))

    def remove_user_from_folder(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/RemoveUserFromFolder", data=data))

    def remove_virtual_space_from_folder(self, data: dict) -> dict:
        return self._data(self._post("DocumentContainer/RemoveVirtualSpaceFromFolder", data=data))

    # TR Documents
    def get_tr_documents(self, params: dict | None = None) -> dict:
        return self._data(self._get("DocumentContainer/GetTrDocuments", params=params))

    def get_tr_document_details(self, doc_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetTrDocumentDetails", params={"id": doc_id}))

    def get_tr_document_types(self) -> dict:
        return self._data(self._get("DocumentContainer/GetTrDocumentTypes"))

    # Person group / Virtual space details
    def get_doc_person_group_details(self, group_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetPersonGroupDetails", params={"id": group_id}))

    def get_doc_person_group_members(self, group_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetPersonGroupMembers", params={"id": group_id}))

    def get_doc_virtual_space_details(self, space_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetVirtualSpaceDetails", params={"id": space_id}))

    def get_doc_virtual_space_members(self, space_id: str) -> dict:
        return self._data(self._get("DocumentContainer/GetVirtualSpaceMembers", params={"id": space_id}))

    def get_doc_virtual_space_types(self) -> dict:
        return self._data(self._get("DocumentContainer/GetVirtualSpaceTypes"))

    # ===================================================================
    # FILE HANDLER (11 endpoints)
    # ===================================================================

    def file_up_start(self, data: dict) -> dict:
        return self._data(self._post("FileHandler/FileUpStart", data=data))

    def file_up(self, data: dict) -> dict:
        return self._data(self._post("FileHandler/FileUp", data=data))

    def file_up_end(self, data: dict) -> dict:
        return self._data(self._post("FileHandler/FileUpEnd", data=data))

    def delete_from_temp(self, data: dict) -> dict:
        return self._data(self._post("FileHandler/DeleteFromTemp", data=data))

    def download_file_documentation_or_zip(self, params: dict) -> dict:
        return self._data(self._get("FileHandler/DownloadDocumentationOrZip", params=params))

    def get_default_language_for_documentations(self) -> dict:
        return self._data(self._get("FileHandler/GetDefaultLanguageForDocumentations"))

    def get_documentations_upload_info(self) -> dict:
        return self._data(self._get("FileHandler/GetDocumentationsUpLoadInfo"))

    def get_file_documentation_types(self) -> dict:
        return self._data(self._get("FileHandler/GetDocumentationTypes"))

    def get_document_library_list(self) -> dict:
        return self._data(self._get("FileHandler/GetDocumentLibraryList"))

    def get_document_library_list_for_message_attachment(self) -> dict:
        return self._data(self._get("FileHandler/GetDocumentLibraryListForMessageAttachment"))

    def generate_guid_for_file_from_document_library(self, data: dict) -> dict:
        return self._data(self._post("FileHandler/GenerateGuidForFileFromDocumentLibrary", data=data))

    # ===================================================================
    # REQUEST FORM (26 endpoints)
    # ===================================================================

    def get_number_of_request_forms(self) -> dict:
        return self._data(self._get("RequestForm/GetNumberOfRequestForms"))

    def get_student_request_form_templates(self) -> dict:
        return self._data(self._get("RequestForm/GetStudentRequestFormTemplates"))

    def get_student_request_form_template_details(self, template_id: str) -> dict:
        return self._data(self._get("RequestForm/GetStudentRequestFormTemplateDetails", params={"id": template_id}))

    def get_started_request_form_templates(self) -> dict:
        return self._data(self._get("RequestForm/GetStartedRequestFormTemplates"))

    def get_started_request_form_template_details(self, template_id: str) -> dict:
        return self._data(self._get("RequestForm/GetStartedRequestFormTemplateDetails", params={"id": template_id}))

    def get_submitted_request_forms(self) -> dict:
        return self._data(self._get("RequestForm/GetSubmittedRequestForms"))

    def get_submitted_request_form_details(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/GetSubmittedRequestFormTemplateDetails", params={"id": form_id}))

    def get_sent_back_request_forms(self) -> dict:
        return self._data(self._get("RequestForm/GetSentBackToCorrectionRequestForms"))

    def get_sent_back_request_form_details(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/GetSentBackToCorrectionRequestFormTemplateDetails", params={"id": form_id}))

    def get_invalidated_request_forms(self) -> dict:
        return self._data(self._get("RequestForm/GetInvalidatedRequestForms"))

    def get_invalidated_request_form_details(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/GetInvalidatedRequestFormDetails", params={"id": form_id}))

    def get_request_form_scores(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/GetScores", params={"id": form_id}))

    def get_request_form_total_score(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/GetTotalScore", params={"id": form_id}))

    def get_request_form_attachments(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/GetAttachments", params={"id": form_id}))

    def get_request_form_attachment_details(self, attachment_id: str) -> dict:
        return self._data(self._get("RequestForm/GetAttachmentDetails", params={"id": attachment_id}))

    def get_request_form_attach_appendix_info(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/GetAttachAppendixInfo", params={"id": form_id}))

    def save_request_form_attachments(self, data: dict) -> dict:
        return self._data(self._post("RequestForm/SaveAttachments", data=data))

    def delete_request_form_attachment(self, attachment_id: str) -> dict:
        return self._data(self._post("RequestForm/DeleteAttachment", data={"id": attachment_id}))

    def get_document_library_for_request_form(self) -> dict:
        return self._data(self._get("RequestForm/GetDocumentLibraryListForRequestForm"))

    def download_request_form(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/DownloadRequestForm", params={"id": form_id}))

    def download_request_form_attachments(self, params: dict) -> dict:
        return self._data(self._get("RequestForm/DownloadAttachments", params=params))

    def download_request_form_forms(self, params: dict) -> dict:
        return self._data(self._get("RequestForm/DownloadForms", params=params))

    def download_request_form_judgement_documents(self, params: dict) -> dict:
        return self._data(self._get("RequestForm/DownloadJudgementDocuments", params=params))

    def download_request_form_resolution(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/DownloadResolution", params={"id": form_id}))

    def view_request_form_filings(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/ViewFilings", params={"id": form_id}))

    def view_request_form_opinions(self, form_id: str) -> dict:
        return self._data(self._get("RequestForm/ViewOpinions", params={"id": form_id}))

    # ===================================================================
    # REQUEST FORM CORE (36 endpoints)
    # ===================================================================

    def get_student_request_form(self) -> dict:
        return self._data(self._get("RequestFormCore/GetStudentRequestForm"))

    def get_request_form_current_page(self, form_id: str) -> dict:
        return self._data(self._get("RequestFormCore/GetCurrentPage", params={"id": form_id}))

    def save_request_form_page_next(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/SavePageAndStepNext", data=data))

    def save_request_form_page_prev(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/SavePageAndStepPrevious", data=data))

    def submit_request_form(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/Submit", data=data))

    def interrupt_request_form(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/Interrupt", data=data))

    def invalidate_request_form(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/Invalidate", data=data))

    def revoke_request_form(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/Revoke", data=data))

    def get_request_form_for_correction(self, form_id: str) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForCorrection", params={"id": form_id}))

    def get_request_form_for_subject(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForSubject", params=params))

    def get_request_form_for_exam(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForExam", params=params))

    def get_request_form_for_imposition(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForImposition", params=params))

    def get_request_form_for_registration(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForRegistration", params=params))

    def get_request_form_for_subject_equivalence(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForSubjectEquivalence", params=params))

    def get_request_form_for_drop_out(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForDropOut", params=params))

    def get_request_form_for_fairness_exam(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForFairnessExam", params=params))

    def get_request_form_for_final_exam(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForFinalExam", params=params))

    def get_request_form_for_legal_remedy(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForLegalRemedy", params=params))

    def get_request_form_for_dormitory(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForDormitory", params=params))

    def get_request_form_for_erasmus(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForErasmus", params=params))

    def get_request_form_for_thesis_application(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForThesisApplication", params=params))

    def get_request_form_for_unique_thesis(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForUniqueThesisApplication", params=params))

    def get_request_form_for_syllabus_from_client(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormForSyllabusFromClient", params=params))

    def get_request_form_attachment_types(self) -> dict:
        return self._data(self._get("RequestFormCore/GetRequestFormAttachmentTypes"))

    def get_number_of_request_form_attachments(self, form_id: str) -> dict:
        return self._data(self._get("RequestFormCore/GetNumberOfAttachments", params={"id": form_id}))

    def get_request_form_documentation_type_id(self) -> dict:
        return self._data(self._get("RequestFormCore/GetDocumentationTypeId"))

    def get_doc_library_for_request_form_at_filling(self, form_id: str) -> dict:
        return self._data(self._get("RequestFormCore/GetDocumentLibraryListForRequestFormAtFilling", params={"id": form_id}))

    def get_doc_library_for_request_form_field_at_filling(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetDocumentLibraryListForRequestFormFieldAtFilling", params=params))

    def get_docs_attached_for_request_form_at_filling(self, form_id: str) -> dict:
        return self._data(self._get("RequestFormCore/GetDocumentationsAttachedForRequestFormAtFilling", params={"id": form_id}))

    def get_docs_attached_for_request_form_field_at_filling(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/GetDocumentationsAttachedForRequestFormFieldAtFilling", params=params))

    def save_attachments_at_filling(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/SaveAttachmentsAtFilling", data=data))

    def interrupt_due_to_document_upload(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/InterruptDueToDocumentUpload", data=data))

    def interrupt_due_to_field_document_upload(self, data: dict) -> dict:
        return self._data(self._post("RequestFormCore/InterruptDueToFieldDocumentUpload", data=data))

    def download_reason_for_repair_document(self, params: dict) -> dict:
        return self._data(self._get("RequestFormCore/DownloadReasonForRepairDocument", params=params))

    def generate_request_form_pdf(self, form_id: str) -> dict:
        return self._data(self._get("RequestFormCore/GenerateRequestFormPdf", params={"id": form_id}))

    # ===================================================================
    # SEMESTER REGISTRATION (5 endpoints)
    # ===================================================================

    def get_semester_registration_term_status(self) -> dict:
        return self._data(self._get("SemesterRegistration/GetTermDataStatusInfo"))

    def is_semester_status_enabled_by_meta(self) -> dict:
        return self._data(self._get("SemesterRegistration/IsSemesterStatusEnabledByMeta"))

    def list_documents_related_to_semester_registration(self) -> dict:
        return self._data(self._get("SemesterRegistration/ListDocumentsReleatedToSemesterRegistration"))

    def get_semester_sent_back_request_form(self, form_id: str) -> dict:
        return self._data(self._get("SemesterRegistration/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_semester_submitted_request_form(self, form_id: str) -> dict:
        return self._data(self._get("SemesterRegistration/GetSubmittedRequestFormDetails", params={"id": form_id}))

    # ===================================================================
    # RECLASSIFICATION REQUEST (2 endpoints)
    # ===================================================================

    def get_reclassification_terms(self) -> dict:
        return self._data(self._get("ReclassificationRequest/GetReclassificationTerms"))

    def set_reclassification_request(self, data: dict) -> dict:
        return self._data(self._post("ReclassificationRequest/SetReclassificationRequest", data=data))

    # ===================================================================
    # REGISTRY SHEET (4 endpoints)
    # ===================================================================

    def get_student_averages(self) -> dict:
        return self._data(self._get("RegistrySheet/GetStudentAverages"))

    def get_student_average_detail(self, term_id: str) -> dict:
        return self._data(self._get("RegistrySheet/GetStudentaverageDetail", params={"termId": term_id}))

    def get_registry_sheet_training_term_data(self) -> dict:
        return self._data(self._get("RegistrySheet/GetStudentTrainingTermData"))

    def get_term_independent_accredited_subjects(self) -> dict:
        return self._data(self._get("RegistrySheet/GetTermIndependentAccreditedSubjects"))

    # ===================================================================
    # THREAT (8 endpoints)
    # ===================================================================

    def get_threat_lines_grid_data(self) -> dict:
        return self._data(self._get("Threat/GetThreatLinesGridData"))

    def get_threat_selected_lines_detail(self, params: dict) -> dict:
        return self._data(self._get("Threat/GetSelectedLMLinesDetail", params=params))

    def get_threat_available_request_form(self, template_id: str) -> dict:
        return self._data(self._get("Threat/GetAvailableRequestFormTemplateDetails", params={"id": template_id}))

    def get_threat_request_form_template_list(self) -> dict:
        return self._data(self._get("Threat/GetRequestFormTemplateList"))

    def get_threat_sent_back_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Threat/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_threat_started_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Threat/GetStartedRequestFormDetails", params={"id": form_id}))

    def get_threat_submitted_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Threat/GetSubmittedRequestFormDetails", params={"id": form_id}))

    def get_threat_submitted_request_forms(self) -> dict:
        return self._data(self._get("Threat/GetSubmittedRequestForms"))

    # ===================================================================
    # LEGAL REMEDY (7 endpoints)
    # ===================================================================

    def get_legal_remediable_resolutions(self) -> dict:
        return self._data(self._get("LegalRemedy/GetLegalRemediableResolutions"))

    def get_legal_remedy_resolution_details(self, resolution_id: str) -> dict:
        return self._data(self._get("LegalRemedy/GetLegalRemedyResolutionDetails", params={"id": resolution_id}))

    def get_legal_remedy_available_request_form(self, template_id: str) -> dict:
        return self._data(self._get("LegalRemedy/GetAvailableRequestFormTemplateDetails", params={"id": template_id}))

    def get_legal_remedy_sent_back_request_form(self, form_id: str) -> dict:
        return self._data(self._get("LegalRemedy/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_legal_remedy_started_request_form(self, form_id: str) -> dict:
        return self._data(self._get("LegalRemedy/GetStartedRequestFormDetails", params={"id": form_id}))

    def get_legal_remedy_submitted_request_form(self, form_id: str) -> dict:
        return self._data(self._get("LegalRemedy/GetSubmittedRequestFormDetails", params={"id": form_id}))

    def get_legal_remedy_submitted_request_forms(self) -> dict:
        return self._data(self._get("LegalRemedy/GetSubmittedRequestForms"))

    # ===================================================================
    # DORMITORY (12 endpoints)
    # ===================================================================

    def get_dormitory_dashboard_periods(self) -> dict:
        return self._data(self._get("Dormitory/GetDormitoryDashboardPeriodsData"))

    def get_dormitory_details(self, dormitory_id: str) -> dict:
        return self._data(self._get("Dormitory/GetDormitoryDetails", params={"id": dormitory_id}))

    def get_dormitory_application_periods(self) -> dict:
        return self._data(self._get("Dormitory/GetDormitoriesApplicationPeriodList"))

    def get_optional_dormitories_by_period(self, period_id: str) -> dict:
        return self._data(self._get("Dormitory/GetOptionalDormitoriesByApplicationPeriod", params={"periodId": period_id}))

    def get_selected_dormitory_period_details(self, period_id: str) -> dict:
        return self._data(self._get("Dormitory/GetSelectedDormitoryApplicationPeriodDetails", params={"periodId": period_id}))

    def get_selected_period_dormitories_data(self, period_id: str) -> dict:
        return self._data(self._get("Dormitory/GetSelectedPeriodDormitoriesData", params={"periodId": period_id}))

    def get_signed_in_dormitory_intervals(self) -> dict:
        return self._data(self._get("Dormitory/GetSignedInStudentDormitoryIntervals"))

    def get_dormitory_signin_points_by_period(self, period_id: str) -> dict:
        return self._data(self._get("Dormitory/GetStundentDormitorySignInPointsByPeriod", params={"periodId": period_id}))

    def get_dormitory_sent_back_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Dormitory/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_dormitory_submitted_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Dormitory/GetSubmittedRequestFormDetails", params={"id": form_id}))

    def revoke_applied_dormitory(self, data: dict) -> dict:
        return self._data(self._post("Dormitory/RevokeAppliedDormitory", data=data))

    def signout_from_dormitory_period(self, data: dict) -> dict:
        return self._data(self._post("Dormitory/SigningOutFromSelectedDormitoryApplicationPeriod", data=data))

    # ===================================================================
    # DORMITORY REGISTRATION (4 endpoints)
    # ===================================================================

    def get_active_dormitory_periods(self) -> dict:
        return self._data(self._get("DormitoryRegistration/GetActiveDormitoryPeriods"))

    def get_active_dormitory_period_details(self, period_id: str) -> dict:
        return self._data(self._get("DormitoryRegistration/GetActiveDormitoryPeriodDetails", params={"periodId": period_id}))

    def get_available_dormitories_by_period(self, period_id: str) -> dict:
        return self._data(self._get("DormitoryRegistration/GetAvailableAndSelectedDormitoriesByPeriod", params={"periodId": period_id}))

    def get_started_dormitory_request_form(self) -> dict:
        return self._data(self._get("DormitoryRegistration/GetStartedRequestForm"))

    # ===================================================================
    # FINAL EXAMS (15 endpoints)
    # ===================================================================

    def get_final_exam_active_periods(self) -> dict:
        return self._data(self._get("FinalExams/GetActivePeriods"))

    def get_final_exams_by_period(self, period_id: str) -> dict:
        return self._data(self._get("FinalExams/GetFinalExamsByPeriod", params={"periodId": period_id}))

    def get_final_exams_by_taken_subjects(self) -> dict:
        return self._data(self._get("FinalExams/GetFinalExamsByTakenSubjects"))

    def get_final_exams_for_exam_change(self, params: dict) -> dict:
        return self._data(self._get("FinalExams/GetFinalExamsForExamChange", params=params))

    def get_final_exam_periods_by_tab_type(self, tab_type: str) -> dict:
        return self._data(self._get("FinalExams/GetPeriodsBySelectedTabType", params={"tabType": tab_type}))

    def get_subjects_by_final_exam_period(self, period_id: str) -> dict:
        return self._data(self._get("FinalExams/GetSubjectsByPeriod", params={"periodId": period_id}))

    def get_subject_details_for_final_exam(self, subject_id: str) -> dict:
        return self._data(self._get("FinalExams/GetSubjectDetailsForFinalExam", params={"subjectId": subject_id}))

    def get_final_exam_topics_and_items(self, params: dict) -> dict:
        return self._data(self._get("FinalExams/GetTopicsAndItems", params=params))

    def application_for_final_exam_period(self, data: dict) -> dict:
        return self._data(self._post("FinalExams/ApplicationForPeriod", data=data))

    def cancel_final_exam_period_application(self, data: dict) -> dict:
        return self._data(self._post("FinalExams/CancelPeriodApplication", data=data))

    def cancel_final_exam_topic_application(self, data: dict) -> dict:
        return self._data(self._post("FinalExams/CancelTopicApplication", data=data))

    def modify_final_exam_topic_application(self, data: dict) -> dict:
        return self._data(self._post("FinalExams/ModifyApplicationForTopic", data=data))

    def get_final_exam_request_form_template(self, template_id: str) -> dict:
        return self._data(self._get("FinalExams/GetRequestFormTemplate", params={"id": template_id}))

    def get_final_exam_sent_back_request_form(self, form_id: str) -> dict:
        return self._data(self._get("FinalExams/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_final_exam_submitted_request_form(self, form_id: str) -> dict:
        return self._data(self._get("FinalExams/GetSubmittedRequestFormDetails", params={"id": form_id}))

    # ===================================================================
    # EMATERIAL (28 endpoints)
    # ===================================================================

    def get_ematerials_dashboard(self) -> dict:
        return self._data(self._get("EMaterial/GetEmaterialsToDashboard"))

    def get_ematerial_student_terms(self) -> dict:
        return self._data(self._get("EMaterial/GetStudentTerms"))

    def get_ematerial_student_terms_for_results_card(self) -> dict:
        return self._data(self._get("EMaterial/GetStudentTermsForResultsCardView"))

    def get_course_ematerials(self, params: dict | None = None) -> dict:
        return self._data(self._get("EMaterial/GetCourseEMaterials", params=params))

    def get_course_ematerial_details(self, ematerial_id: str) -> dict:
        return self._data(self._get("EMaterial/GetCourseEMaterialDetails", params={"id": ematerial_id}))

    def get_subject_ematerials(self, params: dict | None = None) -> dict:
        return self._data(self._get("EMaterial/GetSubjectEMaterials", params=params))

    def get_subject_ematerial_detail(self, ematerial_id: str) -> dict:
        return self._data(self._get("EMaterial/GetSubjectEMaterialDetail", params={"id": ematerial_id}))

    def get_general_ematerials(self, params: dict | None = None) -> dict:
        return self._data(self._get("EMaterial/GetGeneralEMaterials", params=params))

    def get_general_ematerial_details(self, ematerial_id: str) -> dict:
        return self._data(self._get("EMaterial/GetGeneralEMaterialDetails", params={"id": ematerial_id}))

    def get_other_virtual_space_ematerials(self, params: dict | None = None) -> dict:
        return self._data(self._get("EMaterial/GetOtherVirtualSpaceEMaterials", params=params))

    def get_other_virtual_space_ematerial_detail(self, ematerial_id: str) -> dict:
        return self._data(self._get("EMaterial/GetOtherVirtualSpaceEMaterialDetail", params={"id": ematerial_id}))

    def get_panopto_ematerials(self) -> dict:
        return self._data(self._get("EMaterial/GetPanoptoEMaterials"))

    def get_panopto_request(self, ematerial_id: str) -> dict:
        return self._data(self._get("EMaterial/GetPanoptoRequest", params={"id": ematerial_id}))

    def get_panopto_ticket(self) -> dict:
        return self._data(self._get("EMaterial/GetPanoptoTicketForCurrentUser"))

    def get_ematerial_language_version(self, ematerial_id: str) -> dict:
        return self._data(self._get("EMaterial/GetEMaterialLanguageVersion", params={"id": ematerial_id}))

    def get_expiring_ematerial_detail(self, ematerial_id: str) -> dict:
        return self._data(self._get("EMaterial/GetExpiringEMaterialDetail", params={"id": ematerial_id}))

    def get_results_card_view(self, params: dict | None = None) -> dict:
        return self._data(self._get("EMaterial/GetResultsCardView", params=params))

    def get_results_card_details(self, params: dict) -> dict:
        return self._data(self._get("EMaterial/GetResultCardDetailsData", params=params))

    def get_filter_type_for_results_card(self) -> dict:
        return self._data(self._get("EMaterial/GetFilterTypeForGetResultsCardView"))

    def get_student_has_email_address(self) -> dict:
        return self._data(self._get("EMaterial/GetStudentHasEmailAddress"))

    def get_xeropan_url(self) -> dict:
        return self._data(self._get("EMaterial/GetXeropanURL"))

    def start_course_ematerial(self, data: dict) -> dict:
        return self._data(self._post("EMaterial/StartCourseEMaterial", data=data))

    def start_general_ematerial(self, data: dict) -> dict:
        return self._data(self._post("EMaterial/StartGeneralEMaterial", data=data))

    def start_subject_ematerial(self, data: dict) -> dict:
        return self._data(self._post("EMaterial/StartSubjectEMaterial", data=data))

    def start_other_virtual_space_ematerial(self, data: dict) -> dict:
        return self._data(self._post("EMaterial/StartOtherVirtualSpaceEMaterial", data=data))

    def select_course_language_and_start_ematerial(self, data: dict) -> dict:
        return self._data(self._post("EMaterial/SelectCourseLanguageAndStartEMaterial", data=data))

    def select_general_language_and_start_ematerial(self, data: dict) -> dict:
        return self._data(self._post("EMaterial/SelectGeneralLanguageAndStartEMaterial", data=data))

    def select_subject_language_and_start_ematerial(self, data: dict) -> dict:
        return self._data(self._post("EMaterial/SelectSubjectLanguageAndStartEMaterial", data=data))

    def select_other_vs_language_and_start_ematerial(self, data: dict) -> dict:
        return self._data(self._post("EMaterial/SelectOtherVirtualSpaceLanguageAndStartEMaterial", data=data))

    # ===================================================================
    # ONLINE OCCASION (24 endpoints)
    # ===================================================================

    def get_next_online_occasion(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetNextOccasion"))

    def get_online_occasion_type(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetOccasionType"))

    def get_all_online_occasions(self, params: dict | None = None) -> dict:
        return self._data(self._get("OnlineOccasion/GetAllOccasions", params=params))

    def get_all_online_occasion_number(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetAllOccasionNumber"))

    def get_online_course_occasions(self, params: dict | None = None) -> dict:
        return self._data(self._get("OnlineOccasion/GetCourse", params=params))

    def get_online_course_details(self, occasion_id: str) -> dict:
        return self._data(self._get("OnlineOccasion/GetCourseDetails", params={"id": occasion_id}))

    def get_online_course_number(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetCourseNumber"))

    def get_online_exam_occasions(self, params: dict | None = None) -> dict:
        return self._data(self._get("OnlineOccasion/GetExam", params=params))

    def get_online_exam_details(self, occasion_id: str) -> dict:
        return self._data(self._get("OnlineOccasion/GetExamDetails", params={"id": occasion_id}))

    def get_online_exam_number(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetExamNumber"))

    def get_online_consultation_occasions(self, params: dict | None = None) -> dict:
        return self._data(self._get("OnlineOccasion/GetConsultation", params=params))

    def get_online_consultation_details(self, occasion_id: str) -> dict:
        return self._data(self._get("OnlineOccasion/GetConsultationDetails", params={"id": occasion_id}))

    def get_online_consultation_number(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetConsultationNumber"))

    def get_online_task_occasions(self, params: dict | None = None) -> dict:
        return self._data(self._get("OnlineOccasion/GetTask", params=params))

    def get_online_task_details(self, occasion_id: str) -> dict:
        return self._data(self._get("OnlineOccasion/GetTaskDetails", params={"id": occasion_id}))

    def get_online_task_number(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetTaskNumber"))

    def get_online_final_exam_occasions(self, params: dict | None = None) -> dict:
        return self._data(self._get("OnlineOccasion/GetFinalExam", params=params))

    def get_online_final_exam_details(self, occasion_id: str) -> dict:
        return self._data(self._get("OnlineOccasion/GetFinalExamDetails", params={"id": occasion_id}))

    def get_online_final_exam_number(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetFinalExamNumber"))

    def get_online_appointment_list(self, params: dict | None = None) -> dict:
        return self._data(self._get("OnlineOccasion/GetOnlineAppointmentList", params=params))

    def get_online_appointment_details(self, appointment_id: str) -> dict:
        return self._data(self._get("OnlineOccasion/GetOnlineAppointmentDetails", params={"id": appointment_id}))

    def get_online_appointments_count(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetOnlineAppointmentsCount"))

    def get_online_appointment_case_type_list(self) -> dict:
        return self._data(self._get("OnlineOccasion/GetOnlineAppointmentCaseTypeList"))

    # ===================================================================
    # APPOINTMENTS (12 endpoints)
    # ===================================================================

    def get_appointments_list(self, params: dict | None = None) -> dict:
        return self._data(self._get("Appointments/GetAppointmentsList", params=params))

    def get_appointment_item_details(self, appointment_id: str) -> dict:
        return self._data(self._get("Appointments/GetAppointmentItemDetails", params={"id": appointment_id}))

    def get_past_appointments_list(self, params: dict | None = None) -> dict:
        return self._data(self._get("Appointments/GetPastAppointmentsList", params=params))

    def get_new_appointment_reservation_list(self) -> dict:
        return self._data(self._get("Appointments/GetNewAppointmentReservationList"))

    def get_case_office_list(self) -> dict:
        return self._data(self._get("Appointments/GetCaseOfficeList"))

    def get_case_type_list(self) -> dict:
        return self._data(self._get("Appointments/GetCaseTypeList"))

    def get_case_type_methods(self, case_type_id: str) -> dict:
        return self._data(self._get("Appointments/GetCaseTypeMethods", params={"caseTypeId": case_type_id}))

    def get_appointments_printable_template_type_id(self) -> dict:
        return self._data(self._get("Appointments/GetPrintableTemplateTypeId"))

    def insert_new_appointment(self, data: dict) -> dict:
        return self._data(self._post("Appointments/InsertNewAppointment", data=data))

    def insert_message_for_appointment(self, data: dict) -> dict:
        return self._data(self._post("Appointments/InsertMessageForAppointment", data=data))

    def delete_appointment_item(self, appointment_id: str) -> dict:
        return self._data(self._post("Appointments/DeleteAppointmentItem", data={"id": appointment_id}))

    # ===================================================================
    # BOOKING (27 endpoints)
    # ===================================================================

    def get_booking_room_site_list(self) -> dict:
        return self._data(self._get("Booking/GetRoomSiteList"))

    def get_booking_room_building_list(self, site_id: str) -> dict:
        return self._data(self._get("Booking/GetRoomBuildingList", params={"siteId": site_id}))

    def get_booking_room_condition_types(self) -> dict:
        return self._data(self._get("Booking/GetRoomConditionTypes"))

    def get_booking_room_request_types(self) -> dict:
        return self._data(self._get("Booking/GetRoomRequestTypes"))

    def get_booking_room_request_statuses(self) -> dict:
        return self._data(self._get("Booking/GetRoomRequestStatuses"))

    def get_free_rooms_list(self, params: dict) -> dict:
        return self._data(self._get("Booking/GetFreeRoomsList", params=params))

    def get_details_for_new_room_booking(self, params: dict) -> dict:
        return self._data(self._get("Booking/GetDetailsForNewRoomBooking", params=params))

    def insert_new_room_bookings(self, data: dict) -> dict:
        return self._data(self._post("Booking/InsertNewRoomBookings", data=data))

    def get_requested_rooms(self, params: dict | None = None) -> dict:
        return self._data(self._get("Booking/GetRequestedRooms", params=params))

    def get_requested_rooms_list(self, params: dict | None = None) -> dict:
        return self._data(self._get("Booking/GetRequestedRoomsList", params=params))

    def get_requested_room_details(self, room_id: str) -> dict:
        return self._data(self._get("Booking/GetRequestedRoomDetails", params={"id": room_id}))

    def get_reserved_rooms(self, params: dict | None = None) -> dict:
        return self._data(self._get("Booking/GetReservedRooms", params=params))

    def get_reserved_rooms_list(self, params: dict | None = None) -> dict:
        return self._data(self._get("Booking/GetReservedRoomsList", params=params))

    def get_reserved_room_details(self, room_id: str) -> dict:
        return self._data(self._get("Booking/GetReservedRoomDetails", params={"id": room_id}))

    def get_terms_with_requested_rooms(self) -> dict:
        return self._data(self._get("Booking/GetTermsWithRequestedRooms"))

    def get_terms_with_reserved_rooms(self) -> dict:
        return self._data(self._get("Booking/GetTermsWithReservedRooms"))

    def get_terms_with_requested_or_reserved_rooms(self) -> dict:
        return self._data(self._get("Booking/GetTermsWithRequestedOrReservedRooms"))

    def get_total_requested_rooms_count(self) -> dict:
        return self._data(self._get("Booking/GetTotalRequestedRoomsCount"))

    def get_total_reserved_rooms_count(self) -> dict:
        return self._data(self._get("Booking/GetTotalReservedRoomsCount"))

    def get_previous_requested_rooms(self, params: dict | None = None) -> dict:
        return self._data(self._get("Booking/GetPreviousRequestedRoomsList", params=params))

    def get_previous_reserved_rooms(self, params: dict | None = None) -> dict:
        return self._data(self._get("Booking/GetPreviousReservedRoomsList", params=params))

    def get_previous_reserved_and_requested_rooms(self, params: dict | None = None) -> dict:
        return self._data(self._get("Booking/GetPreviousReservedAndRequestedRooms", params=params))

    def get_request_details(self, request_id: str) -> dict:
        return self._data(self._get("Booking/GetRequestDetails", params={"id": request_id}))

    def get_request_details_requested_rooms(self, request_id: str) -> dict:
        return self._data(self._get("Booking/GetRequestDetailsRequestedRoomsList", params={"id": request_id}))

    def get_request_details_reserved_rooms(self, request_id: str) -> dict:
        return self._data(self._get("Booking/GetRequestDetailsReservedRoomsList", params={"id": request_id}))

    def withdraw_room_request(self, data: dict) -> dict:
        return self._data(self._post("Booking/WithdrawRoomRequest", data=data))

    # ===================================================================
    # ROOM SCHEDULE (11 endpoints)
    # ===================================================================

    def get_room_schedule_sites(self) -> dict:
        return self._data(self._get("RoomSchedule/GetSites"))

    def get_room_schedule_buildings(self, site_id: str) -> dict:
        return self._data(self._get("RoomSchedule/GetBuildings", params={"siteId": site_id}))

    def get_room_schedule_organizations(self) -> dict:
        return self._data(self._get("RoomSchedule/GetOrganizations"))

    def get_room_schedule_rooms(self, params: dict) -> dict:
        return self._data(self._get("RoomSchedule/GetRooms", params=params))

    def get_rooms_schedules(self, params: dict) -> dict:
        return self._data(self._get("RoomSchedule/GetRoomsSchedules", params=params))

    def get_classroom_reservation_details(self, reservation_id: str) -> dict:
        return self._data(self._get("RoomSchedule/GetClassRoomReservationDetails", params={"id": reservation_id}))

    def get_consultation_room_reservation_details(self, reservation_id: str) -> dict:
        return self._data(self._get("RoomSchedule/GetConsultationReservationDetails", params={"id": reservation_id}))

    def get_exam_room_reservation_details(self, reservation_id: str) -> dict:
        return self._data(self._get("RoomSchedule/GetExamReservationDetails", params={"id": reservation_id}))

    def get_final_exam_room_reservation_details(self, reservation_id: str) -> dict:
        return self._data(self._get("RoomSchedule/GetFinalExamReservationDetails", params={"id": reservation_id}))

    def get_general_room_reservation_details(self, reservation_id: str) -> dict:
        return self._data(self._get("RoomSchedule/GetGeneralReservationDetails", params={"id": reservation_id}))

    def get_task_room_reservation_details(self, reservation_id: str) -> dict:
        return self._data(self._get("RoomSchedule/GetTaskReservationDetails", params={"id": reservation_id}))

    # ===================================================================
    # ERASMUS (15 endpoints)
    # ===================================================================

    def get_erasmus_applications(self) -> dict:
        return self._data(self._get("Erasmus/GetErasmusApplicationsByStudent"))

    def insert_erasmus_theory_application(self, data: dict) -> dict:
        return self._data(self._post("Erasmus/InsertErasmusTheoryApplication", data=data))

    def insert_erasmus_practice_application(self, data: dict) -> dict:
        return self._data(self._post("Erasmus/InsertErasmusPracticeApplication", data=data))

    def insert_erasmus_theory_and_practice_application(self, data: dict) -> dict:
        return self._data(self._post("Erasmus/InsertErasmusTheoryAndPracticeApplication", data=data))

    def update_erasmus_theory_application(self, data: dict) -> dict:
        return self._data(self._post("Erasmus/UpdateErasmusTheoryApplication", data=data))

    def update_erasmus_practice_application(self, data: dict) -> dict:
        return self._data(self._post("Erasmus/UpdateErasmusPracticeApplication", data=data))

    def update_erasmus_theory_and_practice_application(self, data: dict) -> dict:
        return self._data(self._post("Erasmus/UpdateErasmusTheoryAndPracticeApplication", data=data))

    def get_erasmus_registration_form_type_ids(self) -> dict:
        return self._data(self._get("Erasmus/GetErasmusRegistrationFormTypeIds"))

    def get_erasmus_learning_contract_form_type_ids(self) -> dict:
        return self._data(self._get("Erasmus/GetErasmusLearningContractFormTypeIds"))

    def get_erasmus_practice_contract_form_type_ids(self) -> dict:
        return self._data(self._get("Erasmus/GetErasmusPracticeContractFormTypeIds"))

    def get_erasmus_support_contract_form_type_ids(self) -> dict:
        return self._data(self._get("Erasmus/GetErasmusSupportContractFormTypeIds"))

    def get_erasmus_learning_certificate_form_type_ids(self) -> dict:
        return self._data(self._get("Erasmus/GetErasmusLearningCertificateOfCompletionFormTypeIds"))

    def get_erasmus_practice_certificate_form_type_ids(self) -> dict:
        return self._data(self._get("Erasmus/GetErasmusPracticeCertificateOfCompletionFormTypeIds"))

    def get_erasmus_certificate_of_duration_form_type_ids(self) -> dict:
        return self._data(self._get("Erasmus/GetErasmusCertificateOfDurationFormTypeIds"))

    def get_erasmus_sent_back_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Erasmus/GetSentBackToCorrectionRequestFormDetails", params={"id": form_id}))

    def get_erasmus_submitted_request_form(self, form_id: str) -> dict:
        return self._data(self._get("Erasmus/GetSubmittedRequestFormDetails", params={"id": form_id}))

    # ===================================================================
    # MODULE SELECTION (16 endpoints)
    # ===================================================================

    def get_module_selection_terms(self) -> dict:
        return self._data(self._get("ModuleSelection/GetTerms"))

    def get_module_selection_periods(self) -> dict:
        return self._data(self._get("ModuleSelection/GetModuleSelectionPeriods"))

    def get_module_selection_periods_count(self) -> dict:
        return self._data(self._get("ModuleSelection/GetPeriodsCount"))

    def get_active_module_periods_count(self) -> dict:
        return self._data(self._get("ModuleSelection/GetActivePeriodsCount"))

    def get_module_selection_base_data(self, period_id: str) -> dict:
        return self._data(self._get("ModuleSelection/GetModuleSelectionBaseData", params={"periodId": period_id}))

    def get_module_selection_cards(self, params: dict) -> dict:
        return self._data(self._get("ModuleSelection/GetModuleSelectionCards", params=params))

    def get_module_kinds(self) -> dict:
        return self._data(self._get("ModuleSelection/GetModuleKinds"))

    def get_module_details(self, module_id: str) -> dict:
        return self._data(self._get("ModuleSelection/GetModuleDetails", params={"id": module_id}))

    def get_selected_modules(self, params: dict) -> dict:
        return self._data(self._get("ModuleSelection/GetSelectedModules", params=params))

    def get_choosed_modules(self, params: dict) -> dict:
        return self._data(self._get("ModuleSelection/GetChoosedModules", params=params))

    def get_modules_with_choice_number(self, params: dict) -> dict:
        return self._data(self._get("ModuleSelection/GetModulesWithChoiceNumber", params=params))

    def get_students_by_module(self, module_id: str) -> dict:
        return self._data(self._get("ModuleSelection/GetStudentsByModule", params={"moduleId": module_id}))

    def module_signin(self, data: dict) -> dict:
        return self._data(self._post("ModuleSelection/ModuleSignIn", data=data))

    def module_signout(self, data: dict) -> dict:
        return self._data(self._post("ModuleSelection/ModuleSignOut", data=data))

    def modify_selected_module_choice_number(self, data: dict) -> dict:
        return self._data(self._post("ModuleSelection/ModifySelectedModuleChoiceNumber", data=data))

    # ===================================================================
    # SPECIALIZATION (5 endpoints)
    # ===================================================================

    def get_specialization_list_data(self) -> dict:
        return self._data(self._get("Specialization/GetSpecializationListData"))

    def get_selected_specialization_period_data(self, period_id: str) -> dict:
        return self._data(self._get("Specialization/GetSelectedSpecializationPeriodData", params={"periodId": period_id}))

    def change_selected_specialization(self, data: dict) -> dict:
        return self._data(self._post("Specialization/ChangeSelectedSpecialization", data=data))

    def rollback_selected_specialization(self, data: dict) -> dict:
        return self._data(self._post("Specialization/RollbackSelectedSpecialization", data=data))

    def switch_specialization(self, data: dict) -> dict:
        return self._data(self._post("Specialization/SwitchSpecialization", data=data))

    # ===================================================================
    # THESIS APPLICATION (29 endpoints)
    # ===================================================================

    def get_student_valid_thesis_intervals(self) -> dict:
        return self._data(self._get("ThesisApplication/GetStudentValidThesisIntervals"))

    def get_thesis_interval_details(self, interval_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetThesisIntervalDetails", params={"id": interval_id}))

    def get_thesis_interval_head_data(self, interval_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetThesisIntervalHeadData", params={"id": interval_id}))

    def get_thesis_topics_by_student(self, params: dict | None = None) -> dict:
        return self._data(self._get("ThesisApplication/GetThesisTopicsByStudent", params=params))

    def get_thesis_topic_details(self, topic_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetThesisTopicDetails", params={"id": topic_id}))

    def get_thesis_topic_tutors(self, topic_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetThesisTopicTutorsByTopic", params={"topicId": topic_id}))

    def get_thesis_topic_tutor_strength(self, tutor_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetThesisTopicTutorStrengthData", params={"tutorId": tutor_id}))

    def get_tutors_statement_of_thesis(self, params: dict) -> dict:
        return self._data(self._get("ThesisApplication/GetTutorsStatementOfThesis", params=params))

    def get_title_and_topic_draft_for_thesis(self, params: dict) -> dict:
        return self._data(self._get("ThesisApplication/GetTitleAndTopicDraftDataForThesisApplication", params=params))

    def get_thesis_applications_sort_enabled(self) -> dict:
        return self._data(self._get("ThesisApplication/GetApplicationsSortFunctionEnabled"))

    def get_student_thesis_intervals_sortable(self) -> dict:
        return self._data(self._get("ThesisApplication/GetStudentThesisIntervalsAndApplicationsWhereApplicationsSortable"))

    def set_thesis_application_order(self, data: dict) -> dict:
        return self._data(self._post("ThesisApplication/SetThesisApplicationOrder", data=data))

    def collect_data_for_thesis_application(self, params: dict) -> dict:
        return self._data(self._get("ThesisApplication/CollectDataForThesisApplication", params=params))

    def thesis_application(self, data: dict) -> dict:
        return self._data(self._post("ThesisApplication/ThesisApplication", data=data))

    def insert_new_thesis_application_request(self, data: dict) -> dict:
        return self._data(self._post("ThesisApplication/InsertNewThesisApplictionRequest", data=data))

    def cancel_thesis_application(self, data: dict) -> dict:
        return self._data(self._post("ThesisApplication/CancelThesisApplication", data=data))

    def save_topic_draft_modifications(self, data: dict) -> dict:
        return self._data(self._post("ThesisApplication/SaveTopicDraftModifications", data=data))

    def get_thesis_topic_application_request_templates(self) -> dict:
        return self._data(self._get("ThesisApplication/GetThesisTopicApplicationRequestFormTemplateList"))

    def get_unique_topic_application_request_templates(self) -> dict:
        return self._data(self._get("ThesisApplication/GetUniqueTopicApplicationRequestFormTemplateList"))

    def get_thesis_available_request_form(self, template_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetAvailableRequestFormTemplateDetails", params={"id": template_id}))

    def get_thesis_available_request_form_unique(self, template_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetAvailableRequestFormTemplateDetailsForUniqueTopic", params={"id": template_id}))

    def get_thesis_started_request_form(self, form_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetStartedRequestFormDetails", params={"id": form_id}))

    def get_thesis_started_request_form_unique(self, form_id: str) -> dict:
        return self._data(self._get("ThesisApplication/GetStartedRequestFormDetailsForUniqueTopic", params={"id": form_id}))

    def get_thesis_documentations_type_id(self) -> dict:
        return self._data(self._get("ThesisApplication/GetDocumentationsTypeId"))

    # EVOP thesis
    def get_evop_thesis_topics(self) -> dict:
        return self._data(self._get("ThesisApplication/GetEvopThesisTopicsByStudent"))

    def exists_evop_thesis_topic(self) -> dict:
        return self._data(self._get("ThesisApplication/ExistsEvopThesisTopicForStudent"))

    def get_evop_thesis_topic_languages(self) -> dict:
        return self._data(self._get("ThesisApplication/GetEvopThesisTopicLanguages"))

    def cancel_evop_thesis_application(self, data: dict) -> dict:
        return self._data(self._post("ThesisApplication/CancelEvopThesisApplication", data=data))

    # ===================================================================
    # MANAGE THESIS (13 endpoints)
    # ===================================================================

    def get_common_thesis_applications(self) -> dict:
        return self._data(self._get("CommonThesis/GetThesisApplicationsAndThesisesByStudent"))

    def collect_data_for_thesis_upload(self, params: dict) -> dict:
        return self._data(self._get("ManageThesis/CollectDataForThesisUpload", params=params))

    def get_extra_fields_for_thesis_upload(self, params: dict) -> dict:
        return self._data(self._get("ManageThesis/GetExtraFieldsForThesisUpload", params=params))

    def get_allowed_thesis_documentation_types(self) -> dict:
        return self._data(self._get("ManageThesis/GetAllowedThesisDocumentationTypes"))

    def get_thesis_consultation_data(self, thesis_id: str) -> dict:
        return self._data(self._get("ManageThesis/GetThesisConsultationData", params={"thesisId": thesis_id}))

    def get_thesis_form_type(self) -> dict:
        return self._data(self._get("ManageThesis/GetThesisFormType"))

    def get_thesis_reviews(self, thesis_id: str) -> dict:
        return self._data(self._get("ManageThesis/GetThesisReviews", params={"thesisId": thesis_id}))

    def get_thesis_secrecy_list(self) -> dict:
        return self._data(self._get("ManageThesis/GetThesisSecrecyList"))

    def get_title_and_topic_draft_for_thesis_manage(self, params: dict) -> dict:
        return self._data(self._get("ManageThesis/GetTitleAndTopicDraftDataForThesis", params=params))

    def upload_thesis_files_and_save(self, data: dict) -> dict:
        return self._data(self._post("ManageThesis/UploadThesisFilesAndSaveData", data=data))

    def save_thesis_topic_draft_modifications(self, data: dict) -> dict:
        return self._data(self._post("ManagethesisSavetopicdraftmodifications", data=data))

    def download_all_thesis_review_documents(self, thesis_id: str) -> dict:
        return self._data(self._get("ManageThesis/DownloadAllReviewDocuments", params={"thesisId": thesis_id}))

    def download_thesis_documentation_or_zip(self, params: dict) -> dict:
        return self._data(self._get("ManageThesis/DownloadDocumentationOrZip", params=params))

    def init_thesis_data_for_fas(self, params: dict) -> dict:
        return self._data(self._get("ManageThesis/InitDataForFAS", params=params))

    def save_thesis_fas(self, data: dict) -> dict:
        return self._data(self._post("ManageThesis/SaveFAS", data=data))

    # ===================================================================
    # PUBLISHED THESES (4 endpoints)
    # ===================================================================

    def get_published_theses(self, params: dict | None = None) -> dict:
        return self._data(self._get("PublishedTheses/GetPublishedTheses", params=params))

    def get_published_thesis(self, thesis_id: str) -> dict:
        return self._data(self._get("PublishedTheses/GetPublishedThesis", params={"id": thesis_id}))

    def get_published_theses_organizations(self) -> dict:
        return self._data(self._get("PublishedTheses/GetPublishedThesisesInteriorOrganizations"))

    def download_published_thesis_documentations(self, params: dict) -> dict:
        return self._data(self._get("PublishedTheses/DownloadDocumentations", params=params))

    # ===================================================================
    # PRACTICE (21 endpoints)
    # ===================================================================

    def get_practices_list(self) -> dict:
        return self._data(self._get("Practice/GetPracticesList"))

    def get_practice_list_permissions(self) -> dict:
        return self._data(self._get("Practice/GetPracticeListPermissions"))

    def get_practice_data(self, practice_id: str) -> dict:
        return self._data(self._get("Practice/GetPracticeData", params={"id": practice_id}))

    def get_practice_index_lines(self) -> dict:
        return self._data(self._get("Practice/GetPracticeIndexlines"))

    def get_practice_index_line_details(self, line_id: str) -> dict:
        return self._data(self._get("Practice/GetPracticeIndexLineDetails", params={"id": line_id}))

    def get_practice_documents(self, practice_id: str) -> dict:
        return self._data(self._get("Practice/GetPracticeDocuments", params={"practiceId": practice_id}))

    def get_practice_document_data(self, doc_id: str) -> dict:
        return self._data(self._get("Practice/GetPracticeDocumentData", params={"id": doc_id}))

    def get_practice_documentation_type_id(self) -> dict:
        return self._data(self._get("Practice/GetDocumentationsTypeId"))

    def get_if_practice_document_upload_allowed(self, practice_id: str) -> dict:
        return self._data(self._get("Practice/GetIfDocumentUploadIsAllowed", params={"practiceId": practice_id}))

    def get_practice_exterior_organizations(self) -> dict:
        return self._data(self._get("Practice/GetExteriorOrganizationList"))

    def get_data_modification_rules_for_practice(self) -> dict:
        return self._data(self._get("Practice/GetDataModificationRulesForInsertPractice"))

    def get_judgement_documents(self, practice_id: str) -> dict:
        return self._data(self._get("Practice/GetJudgementDocuments", params={"practiceId": practice_id}))

    def get_dual_contract_list(self) -> dict:
        return self._data(self._get("Practice/GetDualContratList"))

    def get_dual_contract_data(self, contract_id: str) -> dict:
        return self._data(self._get("Practice/GetDualContractData", params={"id": contract_id}))

    def insert_practice(self, data: dict) -> dict:
        return self._data(self._post("Practice/InsertPractice", data=data))

    def insert_practice_only_organization(self, data: dict) -> dict:
        return self._data(self._post("Practice/InsertPracticeOnlyOrganization", data=data))

    def delete_practice(self, practice_id: str) -> dict:
        return self._data(self._post("Practice/DeletePractice", data={"id": practice_id}))

    def delete_practice_documents(self, data: dict) -> dict:
        return self._data(self._post("Practice/DeleteDocuments", data=data))

    def upload_practice_file(self, data: dict) -> dict:
        return self._data(self._post("Practice/FileUploadToDatabase", data=data))

    def download_practice_judgement_docs(self, params: dict) -> dict:
        return self._data(self._get("Practice/DownloadJudgementDocumentationOrZip", params=params))

    def download_practice_documentation(self, params: dict) -> dict:
        return self._data(self._get("Practice/DownloadPracticeDocumentationOrZip", params=params))

    # ===================================================================
    # EXTERNAL PRACTICE (5 endpoints)
    # ===================================================================

    def get_external_practice_dashboard_intervals(self) -> dict:
        return self._data(self._get("ExternalPractice/GetDashboardIntervalData"))

    def get_external_practice_future_intervals(self) -> dict:
        return self._data(self._get("ExternalPractice/GetFutureIntervals"))

    def get_external_practice_previous_intervals(self) -> dict:
        return self._data(self._get("ExternalPractice/GetPreviousIntervals"))

    def get_external_practice_signed_in_intervals(self) -> dict:
        return self._data(self._get("ExternalPractice/GetSignedInIntervalList"))

    def get_external_practice_signed_in_blocks(self, interval_id: str) -> dict:
        return self._data(self._get("ExternalPractice/GetSignedinBlocksByInterval", params={"intervalId": interval_id}))

    # ===================================================================
    # QUERIES (3 endpoints)
    # ===================================================================

    def get_queries_list_data(self) -> dict:
        return self._data(self._get("Queries/GetQueriesListData"))

    def get_fdl_table_data(self, params: dict | None = None) -> dict:
        return self._data(self._get("Queries/GetFdlTableData", params=params))

    def get_query_parameters_by_template(self, template_id: str) -> dict:
        return self._data(self._get(f"Queries/GetParametersByTemplate/{template_id}"))

    # ===================================================================
    # GENERAL FORM (4 endpoints)
    # ===================================================================

    def get_student_general_forms(self) -> dict:
        return self._data(self._get("GeneralForm/GetStudentGeneralForms"))

    def get_student_general_form_details(self, form_id: str) -> dict:
        return self._data(self._get("GeneralForm/GetStudentGeneralFormDetails", params={"id": form_id}))

    def check_student_general_form_print(self, form_id: str) -> dict:
        return self._data(self._get("GeneralForm/CheckStudentGeneralFormPrint", params={"id": form_id}))

    def download_student_general_form(self, form_id: str) -> dict:
        return self._data(self._get("GeneralForm/DownloadStudentGeneralForm", params={"id": form_id}))

    # ===================================================================
    # PUBLICATION (18 endpoints)
    # ===================================================================

    def get_publications(self, params: dict | None = None) -> dict:
        return self._data(self._get("Publication/GetPublications", params=params))

    def get_publication_base_data(self, pub_id: str) -> dict:
        return self._data(self._get("Publication/BaseData", params={"id": pub_id}))

    def get_publication_details_data(self, pub_id: str) -> dict:
        return self._data(self._get("Publication/DetailsData", params={"id": pub_id}))

    def get_publication_author_data(self, pub_id: str) -> dict:
        return self._data(self._get("Publication/AuthorData", params={"id": pub_id}))

    def get_publication_additional_data(self, pub_id: str) -> dict:
        return self._data(self._get("Publication/AdditionalData", params={"id": pub_id}))

    def get_publication_publish_data(self, pub_id: str) -> dict:
        return self._data(self._get("Publication/PublishData", params={"id": pub_id}))

    def get_publication_update_data(self, pub_id: str) -> dict:
        return self._data(self._get("Publication/GetUpdateData", params={"id": pub_id}))

    def get_insertable_publication_types(self) -> dict:
        return self._data(self._get("Publication/GetInsertablePublicationTypeList"))

    def get_modifiable_publication_types(self) -> dict:
        return self._data(self._get("Publication/GetModifiablePublicationTypeList"))

    def get_publication_interior_organizations(self) -> dict:
        return self._data(self._get("Publication/GetInteriorOrganizations"))

    def get_publication_documentation_type_id(self) -> dict:
        return self._data(self._get("Publication/GetDocumentationsTypeId"))

    def insert_publication_allowed(self) -> dict:
        return self._data(self._get("Publication/InsertPublicationAllowed"))

    def create_publication(self, data: dict) -> dict:
        return self._data(self._post("Publication/CreatePublication", data=data))

    def modify_publication(self, data: dict) -> dict:
        return self._data(self._post("Publication/ModifyPublication", data=data))

    def delete_publications(self, data: dict) -> dict:
        return self._data(self._post("Publication/DeletePublications", data=data))

    def insert_publication_extras(self, data: dict) -> dict:
        return self._data(self._post("Publication/InsertPublicationExtras", data=data))

    def download_publication_document(self, params: dict) -> dict:
        return self._data(self._get("Publication/DownloadDocument", params=params))

    # ===================================================================
    # NOTE SEARCH (2 endpoints)
    # ===================================================================

    def get_notes_list(self, params: dict | None = None) -> dict:
        return self._data(self._get("NoteSearch/GetNotesList", params=params))

    def get_note_details(self, note_id: str) -> dict:
        return self._data(self._get("NoteSearch/GetNoteDetailsData", params={"id": note_id}))

    # ===================================================================
    # FIR (1 endpoint)
    # ===================================================================

    def get_student_fir_data(self) -> dict:
        return self._data(self._get("FIR/GetStudentFIRData"))

    # ===================================================================
    # DKT (1 endpoint)
    # ===================================================================

    def get_dkt_results(self) -> dict:
        return self._data(self._get("DKT/Results"))

    # ===================================================================
    # LOGIN (5 endpoints)
    # ===================================================================

    def get_login_news(self) -> dict:
        return self._data(self._get("Login/GetNews"))

    def get_login_links(self) -> dict:
        return self._data(self._get("Login/GetLinks"))

    def get_login_documents(self) -> dict:
        return self._data(self._get("Login/GetDocuments"))

    def get_login_download(self, params: dict) -> dict:
        return self._data(self._get("Login/Download", params=params))

    def get_login_dkt(self) -> dict:
        return self._data(self._get("Login/DKT"))

    # ===================================================================
    # PRINTABLE TEMPLATES (25 endpoints)
    # ===================================================================

    def get_printable_templates_list(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintableTemplatesList"))

    def check_form_printable_status(self, form_id: str) -> dict:
        return self._data(self._get("PrintableTemplates/CheckFormPrintableStatus", params={"id": form_id}))

    def get_print_calendar(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintCalendar", params=params))

    def get_print_registered_courses_form_type_id(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintRegisteredCoursesFormTypeId"))

    def print_registered_courses(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/PrintRegisteredCourses", params=params))

    def get_print_subject_details_form_type_id(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintSubjectDetailsFormTypeId"))

    def print_subject_details(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/PrintSubjectDetails", params=params))

    def print_subject_details_for_final_exams(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/PrintSubjectDetailsForFinalExams", params=params))

    def get_print_subject_thematics_form_type_id(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintSubjectThematicsFormTypeId"))

    def print_subject_thematics(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/PrintSubjectThematics", params=params))

    def get_statement_of_taken_subjects(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetStatementOfTakenSubjects"))

    def print_blank_exam_form(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/PrintBlankExamFormPerStudent", params=params))

    def get_print_data_modification_history_form_type_id(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintDataModificationHistoryFormTypeId"))

    def print_data_modification_history(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/PrintDataModificationHistory", params=params))

    def get_printable_form_templates_for_fulfillment_sheet(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintableFormTemplatesForFulfillmentSheet"))

    def print_fulfillment_sheet(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/PrintFulfillmentSheet", params=params))

    def get_printable_form_templates_for_registry_sheet(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintableFormTemplatesForRegistrySheet"))

    def print_thesis_data(self, params: dict) -> dict:
        return self._data(self._get("PrintableTemplates/PrintThesisData", params=params))

    def get_print_erasmus_registration(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintErasmusRegistration"))

    def get_print_erasmus_learning_contract(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintErasmusLearningContract"))

    def get_print_erasmus_practice_contract(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintErasmusPracticeContract"))

    def get_print_erasmus_support_contract(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintErasmusSupportContract"))

    def get_print_erasmus_learning_certificate(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintErasmusLearningCertificateOfCompletion"))

    def get_print_erasmus_practice_certificate(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintErasmusPracticeCertificateOfCompletion"))

    def get_print_erasmus_certificate_of_duration(self) -> dict:
        return self._data(self._get("PrintableTemplates/GetPrintErasmusCertificateOfDuration"))

    # ===================================================================
    # MEETSTREET (Virtual Spaces) - ~70 endpoints across sub-controllers
    # ===================================================================

    # MeetStreetMain (28 endpoints)
    def get_virtual_spaces(self, params: dict | None = None) -> dict:
        return self._data(self._get("MeetStreetMain/GetVirtualSpaces", params=params))

    def get_virtual_space_data(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/GetVirtualSpaceData", params={"id": space_id}))

    def get_virtual_space_for_edit(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/GetVirtualSpaceForEdit", params={"id": space_id}))

    def get_virtual_space_members(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/GetVirtualSpaceMembers", params={"id": space_id}))

    def get_virtual_space_activities(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/GetVirtualSpaceActivities", params={"id": space_id}))

    def get_my_virtual_spaces_activities(self) -> dict:
        return self._data(self._get("MeetStreetMain/GetMyVirtualSpacesActivities"))

    def get_favourite_virtual_spaces(self) -> dict:
        return self._data(self._get("MeetStreetMain/GetFavouriteVirtualSpaces"))

    def get_virtual_space_search_parameters(self) -> dict:
        return self._data(self._get("MeetStreetMain/GetVirtualSpaceSearchParameters"))

    def get_attachable_virtual_spaces(self) -> dict:
        return self._data(self._get("MeetStreetMain/GetAttachableVirtualSpaces"))

    def get_new_virtual_space_info(self) -> dict:
        return self._data(self._get("MeetStreetMain/GetNewVirtualSpaceInfo"))

    def can_create_own_virtual_space(self) -> dict:
        return self._data(self._get("MeetStreetMain/CanCreateOwnVirtualSpace"))

    def can_view_virtual_space(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/CanViewVirtualSpace", params={"id": space_id}))

    def has_access_dkt_by_user(self) -> dict:
        return self._data(self._get("MeetStreetMain/HasAccessDKTByUser"))

    def get_all_virtual_space_documents(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/GetAllVirtualSpaceDocuments", params={"id": space_id}))

    def get_all_virtual_space_forums(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/GetAllVirtualSpaceForums", params={"id": space_id}))

    def get_all_virtual_space_news(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/GetAllVirtualSpaceNews", params={"id": space_id}))

    def get_public_news(self) -> dict:
        return self._data(self._get("MeetStreetMain/GetPublicNews"))

    def get_global_forums(self, params: dict | None = None) -> dict:
        return self._data(self._get("MeetStreetMain/GetGlobalForums", params=params))

    def get_global_forum_details(self, forum_id: str) -> dict:
        return self._data(self._get("MeetStreetMain/GetGlobalForumDetails", params={"id": forum_id}))

    def create_new_virtual_space(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetMain/CreateNewVirtualSpace", data=data))

    def update_virtual_space(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetMain/UpdateVirtualSpace", data=data))

    def update_virtual_space_data_for_entered_student(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetMain/UpdateVirtualSpaceDataForEnteredStudent", data=data))

    def set_virtual_space_favourite(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetMain/SetVirtualSpaceFavourite", data=data))

    def leave_virtual_space(self, space_id: str) -> dict:
        return self._data(self._post("MeetStreetMain/LeaveVirtualSpace", data={"id": space_id}))

    def copy_virtual_space_content(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetMain/CopyVirtualSpaceContent", data=data))

    def create_global_forum(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetMain/CreateGlobalForum", data=data))

    def update_global_forum(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetMain/UpdateGlobalForum", data=data))

    def delete_global_forums(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetMain/DeleteGlobalForums", data=data))

    # MeetStreetForum (14 endpoints)
    def get_meetstreet_forums(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetForum/GetForums", params={"virtualSpaceId": space_id}))

    def get_meetstreet_forum_data(self, forum_id: str) -> dict:
        return self._data(self._get("MeetStreetForum/GetForumData", params={"id": forum_id}))

    def get_meetstreet_forum_posts(self, forum_id: str) -> dict:
        return self._data(self._get("MeetStreetForum/GetForumPosts", params={"forumId": forum_id}))

    def get_meetstreet_news_forum(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetForum/GetNewsForum", params={"virtualSpaceId": space_id}))

    def create_meetstreet_forum(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/CreateForum", data=data))

    def update_meetstreet_forum(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/UpdateForum", data=data))

    def create_meetstreet_forum_post(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/CreateForumPost", data=data))

    def update_meetstreet_forum_post(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/UpdateForumPost", data=data))

    def delete_meetstreet_forums(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/DeleteForums", data=data))

    def delete_meetstreet_forum_posts(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/DeleteForumPosts", data=data))

    def close_meetstreet_forums(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/CloseForums", data=data))

    def revoke_meetstreet_forums_closed(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/RevokeForumsClosedState", data=data))

    def revoke_meetstreet_forums_deleted(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/RevokeForumsDeletedState", data=data))

    def set_meetstreet_forum_favourite(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/SetForumFavouriteState", data=data))

    def report_meetstreet_post(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetForum/ReportPost", data=data))

    # MeetStreetNews (4 endpoints)
    def get_meetstreet_news(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetNews/GetVirtualSpaceNews", params={"virtualSpaceId": space_id}))

    def get_meetstreet_news_details(self, news_id: str) -> dict:
        return self._data(self._get("MeetStreetNews/GetNewsDetails", params={"id": news_id}))

    def save_meetstreet_news(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetNews/SaveNews", data=data))

    def delete_meetstreet_news(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetNews/DeleteNews", data=data))

    # MeetStreetEvents (14 endpoints)
    def get_meetstreet_events(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetEvents/GetVirtualSpaceEvents", params={"virtualSpaceId": space_id}))

    def get_meetstreet_my_events(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetEvents/GetVirtualSpaceMyEvents", params={"virtualSpaceId": space_id}))

    def get_meetstreet_other_events(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetEvents/GetVirtualSpaceOtherEvents", params={"virtualSpaceId": space_id}))

    def get_meetstreet_event_details(self, event_id: str) -> dict:
        return self._data(self._get("MeetStreetEvents/GetVirtualSpaceEventDetails", params={"id": event_id}))

    def get_meetstreet_event_members(self, event_id: str) -> dict:
        return self._data(self._get("MeetStreetEvents/GetVirtualSpaceEventMembers", params={"eventId": event_id}))

    def get_meetstreet_excluding_events(self, event_id: str) -> dict:
        return self._data(self._get("MeetStreetEvents/GetExcludingEventsByEvent", params={"eventId": event_id}))

    def get_meetstreet_excluded_events_for_modify(self, event_id: str) -> dict:
        return self._data(self._get("MeetStreetEvents/GetExcludedEventsForModify", params={"eventId": event_id}))

    def create_meetstreet_event(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetEvents/CreateVirtualSpaceEvent", data=data))

    def update_meetstreet_event(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetEvents/UpdateVirtualSpaceEvent", data=data))

    def copy_meetstreet_event(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetEvents/CopyVirtualSpaceEvent", data=data))

    def delete_meetstreet_events(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetEvents/DeleteVirtualSpaceEvents", data=data))

    def signin_meetstreet_event(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetEvents/SignInVirtualSpaceEvent", data=data))

    def signout_meetstreet_event(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetEvents/SignOutVirtualSpaceEvent", data=data))

    # MeetStreetVote (7 endpoints)
    def get_meetstreet_votes(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetVote/GetVotes", params={"virtualSpaceId": space_id}))

    def get_meetstreet_vote_details(self, vote_id: str) -> dict:
        return self._data(self._get("MeetStreetVote/GetVoteDetails", params={"id": vote_id}))

    def get_meetstreet_vote_result(self, vote_id: str) -> dict:
        return self._data(self._get("MeetStreetVote/GetVoteResult", params={"id": vote_id}))

    def create_meetstreet_vote(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetVote/CreateVote", data=data))

    def save_meetstreet_vote(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetVote/SaveVote", data=data))

    def save_meetstreet_vote_details(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetVote/SaveVoteDetails", data=data))

    def delete_meetstreet_votes(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetVote/DeleteVotes", data=data))

    # MeetStreetDocument (2 endpoints)
    def get_meetstreet_documents(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetDocument/GetDocumentsResponse", params={"virtualSpaceId": space_id}))

    def attach_document_to_virtual_space(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetDocument/AttachDocumentToVirtualSpace", data=data))

    # MeetStreetLink (3 endpoints)
    def get_meetstreet_useful_links(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetLink/GetVirtualSpaceUsefulLinks", params={"virtualSpaceId": space_id}))

    def save_meetstreet_useful_link(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetLink/SaveUsefulLink", data=data))

    def delete_meetstreet_useful_links(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetLink/DeleteUsefulLinks", data=data))

    # MeetStreetELearning (5 endpoints)
    def get_meetstreet_elearnings(self, space_id: str) -> dict:
        return self._data(self._get("MeetStreetELearning/GetVirtualSpaceElearnings", params={"virtualSpaceId": space_id}))

    def get_meetstreet_elearning_details(self, elearning_id: str) -> dict:
        return self._data(self._get("MeetStreetELearning/GetVirtualSpaceElearningDetails", params={"id": elearning_id}))

    def get_meetstreet_elearning_extended_data(self, elearning_id: str) -> dict:
        return self._data(self._get("MeetStreetELearning/GetElearningExtendedData", params={"id": elearning_id}))

    def start_meetstreet_elearning(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetELearning/StartElearning", data=data))

    def select_language_and_start_elearning(self, data: dict) -> dict:
        return self._data(self._post("MeetStreetELearning/SelectLanguageAndStartEleraning", data=data))

    # ===================================================================
    # CAPTCHA (2 endpoints)
    # ===================================================================

    def get_captcha_image(self) -> dict:
        return self._data(self._get("captcha/image"))

    def get_captcha_audio(self) -> dict:
        return self._data(self._get("captcha/audio"))

    # ===================================================================
    # AVDH (2 endpoints)
    # ===================================================================

    def request_file_sign(self, data: dict) -> dict:
        return self._data(self._post("Avdh/RequestFileSign", data=data))

    def document_signed_callback(self, data: dict) -> dict:
        return self._data(self._post("AvdhCallback/DocumentSignedCallback", data=data))

    # ===================================================================
    # PAGE NAVIGATION (5 endpoints)
    # ===================================================================

    def get_specified_course_occasion(self, params: dict) -> dict:
        return self._data(self._get("PageNavigation/GetSpecifiedCourseOccasion", params=params))

    def get_specified_exam_occasion(self, params: dict) -> dict:
        return self._data(self._get("PageNavigation/GetSpecifiedExamOccasion", params=params))

    def get_specified_consultation_occasion(self, params: dict) -> dict:
        return self._data(self._get("PageNavigation/GetSpecifiedConsultationOccasion", params=params))

    def get_specified_final_exam_occasion(self, params: dict) -> dict:
        return self._data(self._get("PageNavigation/GetSpecifiedFinalExamOccasion", params=params))

    def get_specified_task_occasion(self, params: dict) -> dict:
        return self._data(self._get("PageNavigation/GetSpecifiedTaskOccasion", params=params))
