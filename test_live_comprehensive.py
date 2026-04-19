"""Comprehensive live test for all major controllers."""
import os
import warnings
warnings.filterwarnings("ignore")
from neptun_api import NeptunAPI
from datetime import datetime

api = NeptunAPI(
    os.environ["NEPTUN_USERNAME"],
    os.environ["NEPTUN_PASSWORD"],
    base_url=os.environ.get("NEPTUN_BASE_URL", "https://neptun.uni-obuda.hu/ujhallgato/api/"),
)
api.authenticate()

results = []

def test(name, fn):
    try:
        r = fn()
        results.append(("PASS", name))
        print(f"PASS  {name}")
    except Exception as e:
        err = str(e)[:120]
        results.append(("FAIL", name, err))
        print(f"FAIL  {name} -> {err}")

# === Gather IDs we need ===
trainings = api.get_trainings()
training_id = trainings[0]["studentTrainingId"] if trainings else None
print(f"  training_id={training_id}")

terms = api.get_taken_subjects_terms()
term_id = terms[0]["value"] if terms else None
print(f"  term_id={term_id}")

training_terms = api.get_student_training_terms()
training_term_id = training_terms[0]["value"] if training_terms else None
print(f"  training_term_id={training_term_id}")

# === General ===
test("get_trainings", lambda: api.get_trainings())
test("get_general_training_data", lambda: api.get_general_training_data())
test("get_extended_menu_permissions", lambda: api.get_extended_menu_permissions())

# === Dashboard ===
test("get_dashboard_actual_term", lambda: api.get_dashboard_actual_term())
test("get_dashboard_averages", lambda: api.get_dashboard_averages())
test("get_dashboard_credit_progress", lambda: api.get_dashboard_credit_progress())
test("get_dashboard_exam_entries", lambda: api.get_dashboard_exam_entries())
test("get_dashboard_actual_term_exam_entries", lambda: api.get_dashboard_actual_term_exam_entries())

# === Messages ===
test("get_received_messages", lambda: api.get_received_messages(0, 20))
test("get_sent_messages", lambda: api.get_sent_messages(0, 20))
test("get_unread_message_count", lambda: api.get_unread_message_count())
test("get_message_settings", lambda: api.get_message_settings())
test("get_message_sending_settings", lambda: api.get_message_sending_settings())
test("get_message_limit_setting", lambda: api.get_message_limit_setting())

# === Calendar ===
s, e = datetime(2025, 9, 1), datetime(2026, 1, 31)
test("get_calendar_events", lambda: api.get_calendar_events(s, e))
test("get_calendar_trainings", lambda: api.get_calendar_trainings())
test("get_calendar_selected_types", lambda: api.get_calendar_selected_types())
test("get_calendar_selected_view", lambda: api.get_calendar_selected_view())
test("get_calendar_export_links", lambda: api.get_calendar_export_links())
test("get_calendar_print_template_ids", lambda: api.get_calendar_print_template_ids())
if training_id:
    test("get_calendar_training_name", lambda: api.get_calendar_training_name(training_id))

# === TakenSubjects ===
test("get_taken_subjects_terms", lambda: api.get_taken_subjects_terms())
if term_id:
    test("get_taken_subjects", lambda: api.get_taken_subjects(term_id))

# === RegisteredCourses ===
test("get_registered_courses_terms", lambda: api.get_registered_courses_terms())

# === Advancement ===
test("get_term_averages", lambda: api.get_term_averages())
test("get_term_independent_accredited_subjects", lambda: api.get_term_independent_accredited_subjects())
test("get_student_training_terms", lambda: api.get_student_training_terms())
if training_term_id:
    test("get_student_training_term_data", lambda: api.get_student_training_term_data(training_term_id))

# === Exam ===
test("get_exam_terms", lambda: api.get_exam_terms())
test("get_consultation_terms", lambda: api.get_consultation_terms())
test("get_exam_results_terms", lambda: api.get_exam_results_terms())

# === Financial ===
test("get_financial_impositions", lambda: api.get_financial_impositions())
test("get_financial_dashboard_visibility", lambda: api.get_financial_dashboard_visibility())
test("get_financial_item_terms", lambda: api.get_financial_item_terms())
test("get_financial_bonuses_terms", lambda: api.get_financial_bonuses_terms())

# === PersonalData ===
test("get_address_type", lambda: api.get_address_type())
test("get_telephone_type", lambda: api.get_telephone_type())
test("get_student_language_exams", lambda: api.get_student_language_exams())
test("get_student_competitions", lambda: api.get_student_competitions())
test("get_personal_data_countries", lambda: api.get_personal_data_countries())
if training_id:
    test("get_personal_data_terms_by_training", lambda: api.get_personal_data_terms_by_training(training_id))

# === StudentCard ===
test("get_student_card_claim", lambda: api.get_student_card_claim())

# === Documents ===
test("get_document_container_student_terms", lambda: api.get_document_container_student_terms())

# === Questionnaires ===
test("get_questionnaire_student_terms", lambda: api.get_questionnaire_student_terms())
test("get_finished_questionnaires", lambda: api.get_finished_questionnaires())

# === Profiles ===
test("get_user_profile_settings", lambda: api.get_user_profile_settings())
test("get_user_profile_default_avatars", lambda: api.get_user_profile_default_avatars())

# === Scholarship ===
test("get_scholarship_payments", lambda: api.get_scholarship_payments())
test("get_scholarship_payment_terms", lambda: api.get_scholarship_payment_terms())

# === RequestForm ===
test("get_request_form_attachment_types", lambda: api.get_request_form_attachment_types())
test("get_request_form_documentation_type_id", lambda: api.get_request_form_documentation_type_id())

# === Semester Registration ===
test("get_semester_registration_term_status", lambda: api.get_semester_registration_term_status())

# === RegistrySheet ===
test("get_registry_sheet_training_term_data", lambda: api.get_registry_sheet_training_term_data())

# === Publication ===
test("get_insertable_publication_types", lambda: api.get_insertable_publication_types())
test("get_modifiable_publication_types", lambda: api.get_modifiable_publication_types())

# === Erasmus ===
test("get_erasmus_applications", lambda: api.get_erasmus_applications())

# === EMaterial ===
test("get_ematerial_student_terms", lambda: api.get_ematerial_student_terms())

# === OnlineOccasion ===
test("get_all_online_occasion_number", lambda: api.get_all_online_occasion_number())
test("get_next_online_occasion", lambda: api.get_next_online_occasion())

# === Booking ===
test("get_booking_room_site_list", lambda: api.get_booking_room_site_list())
sites = None
try:
    sites = api.get_booking_room_site_list()
except Exception:
    pass
if sites and isinstance(sites, list) and len(sites) > 0:
    site_id = sites[0].get("id") or sites[0].get("value") or sites[0].get("siteId", "")
    if site_id:
        test("get_booking_room_building_list", lambda: api.get_booking_room_building_list(str(site_id)))
test("get_booking_room_condition_types", lambda: api.get_booking_room_condition_types())
test("get_booking_room_request_types", lambda: api.get_booking_room_request_types())

# === Dormitory ===
test("get_active_dormitory_periods", lambda: api.get_active_dormitory_periods())

# === FinalExams ===
test("get_final_exam_active_periods", lambda: api.get_final_exam_active_periods())

# === Specialization ===
test("get_current_specializations", lambda: api.get_current_specializations())
test("get_specialization_list_data", lambda: api.get_specialization_list_data())

# === ModuleSelection ===
test("get_active_module_periods_count", lambda: api.get_active_module_periods_count())
test("get_module_selection_terms", lambda: api.get_module_selection_terms())

# === BankAccount ===
test("get_bank_accounts", lambda: api.get_bank_accounts())

# === Tasks ===
test("get_actual_tasks", lambda: api.get_actual_tasks())
test("get_tasks_terms", lambda: api.get_tasks_terms())

# === SubjectApplication ===
test("get_subject_application_terms", lambda: api.get_subject_application_terms())

# === SubjectCourse ===
test("get_subject_course_terms", lambda: api.get_subject_course_terms())

# === Curriculum ===
test("get_curriculum_templates", lambda: api.get_curriculum_templates())

# === RoomSchedule ===
test("get_terms_for_institutional_timetable", lambda: api.get_terms_for_institutional_timetable())

# === ThesisApplication ===
test("get_published_theses", lambda: api.get_published_theses())

# === Practice ===
test("get_data_modification_rules_for_practice", lambda: api.get_data_modification_rules_for_practice())

# === Summary ===
passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
print(f"\n=== {passed} PASS, {failed} FAIL out of {len(results)} ===")
if failed:
    print("\nFailed tests:")
    for r in results:
        if r[0] == "FAIL":
            print(f"  {r[1]} -> {r[2]}")
