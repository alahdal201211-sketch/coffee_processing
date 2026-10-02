import csv
import os
import re

import frappe
from frappe.translate import get_messages_for_app


# Arabic translations for user-facing Coffee Processing messages.
# Internal fieldnames / database identifiers are intentionally NOT translated.
TRANSLATIONS = {
    "Account": "الحساب",
    "Actual input quantity cannot be negative": "لا يمكن أن تكون كمية الإدخال الفعلية سالبة",
    "Actual input quantity must be greater than zero": "يجب أن تكون كمية الإدخال الفعلية أكبر من صفر",
    "Actual output quantity cannot be negative": "لا يمكن أن تكون كمية الإخراج الفعلية سالبة",
    "Amended From": "مُعدّل من",
    "Amount": "المبلغ",
    "Anaerobic": "لاهوائي",
    "Approved": "معتمد",
    "Apps": "التطبيقات",
    "Archived": "مؤرشف",
    "At least one input is required.": "يجب إدخال مصدر واحد على الأقل.",
    "At least one output is required.": "يجب إدخال مخرج واحد على الأقل.",
    "At least one step is required": "يجب إضافة خطوة واحدة على الأقل",
    "At least one stock input is required.": "يجب إدخال عنصر مخزني واحد على الأقل.",
    "At least one stock output is required.": "يجب إدخال مخرج مخزني واحد على الأقل.",
    "At least two batches are required": "يجب إدخال دفعتين على الأقل",
    "Available": "متاح",
    "Avg Cost/KG": "متوسط التكلفة/كجم",
    "Batch Count": "عدد الدفعات",
    "Batch ERPNext": "دفعة ERPNext",
    "Batch No is required for input item {0}.": "رقم الدفعة مطلوب للصنف المدخل {0}.",
    "Batch has no route assigned": "لا يوجد مسار معالجة مخصص للدفعة",
    "Blend": "خلط",
    "Blend must have at least two sources": "يجب أن يحتوي الخلط على مصدرين على الأقل",
    "Blend source quantities do not match total quantity": "كميات مصادر الخلط لا تتطابق مع الكمية الإجمالية",
    "Branch": "الفرع",
    "Branch is required.": "الفرع مطلوب.",
    "By-Product": "منتج ثانوي",
    "By-Product Credit": "رصيد المنتج الثانوي",
    "COGS": "تكلفة البضاعة المباعة",
    "Cost/KG": "التكلفة/كجم",
    "Coffee Type": "نوع البن",
    "Commercial": "تجاري",
    "Completed": "مكتمل",
    "Completed Orders": "الأوامر المكتملة",
    "Company": "الشركة",
    "Company is required.": "الشركة مطلوبة.",
    "Count": "عدد",
    "Cost": "التكلفة",
    "Create": "إنشاء",
    "Customer": "العميل",
    "Daily": "يومي",
    "Date": "التاريخ",
    "Draft": "مسودة",
    "Drying": "تجفيف",
    "English": "الإنجليزية",
    "Fermentation": "تخمير",
    "Full": "كامل",
    "Grade": "الدرجة",
    "Grade Item": "صنف الدرجة",
    "Grade Qty": "كمية الدرجة",
    "Gross Profit": "إجمالي الربح",
    "In Progress": "قيد التنفيذ",
    "Input": "إدخال",
    "Input Qty": "كمية الإدخال",
    "Item Code": "رمز الصنف",
    "Item Name": "اسم الصنف",
    "KG": "كجم",
    "Log out": "تسجيل الخروج",
    "Margin %": "هامش الربح %",
    "Max Cost/KG": "أعلى تكلفة/كجم",
    "Min Cost/KG": "أدنى تكلفة/كجم",
    "Output": "إخراج",
    "Output Qty": "كمية الإخراج",
    "Parent Batch": "الدفعة الأصل",
    "Parent Item": "الصنف الأصل",
    "Parent Qty": "كمية الأصل",
    "Pending Approval": "بانتظار الموافقة",
    "Please select a warehouse.": "يرجى اختيار مستودع.",
    "Processing": "معالجة",
    "Qty (KG)": "الكمية (كجم)",
    "Qty Sold": "الكمية المباعة",
    "Ready": "جاهز",
    "Ready for Processing": "جاهز للمعالجة",
    "Rejected": "مرفوض",
    "Reject": "مرفوض",
    "Revenue": "الإيرادات",
    "Reserved": "محجوز",
    "Sales": "المبيعات",
    "Semi-Washed": "شبه مغسول",
    "Specialty": "مختص",
    "Stock": "المخزون",
    "Total Qty": "إجمالي الكمية",
    "Total Value": "إجمالي القيمة",
    "Value": "القيمة",
    "Warehouse": "المستودع",
    "Yield %": "نسبة الاستخلاص %",
    "Wash": "غسيل",
    "Washed": "مغسول",
    "Raw Coffee": "بن خام",
    "Green Coffee": "بن أخضر",
    "Roasted Coffee": "بن محمص",
    "Dry": "جاف",
    "Wet": "رطب",
    "Cancelled": "ملغى",
    "Pending": "معلق",
    "Yes": "نعم",
    "No": "لا",
    "Inactive": "غير نشط",
    "Active": "نشط",
    "Occupied": "مشغول",
    "Maintenance": "صيانة",
    "Reserved": "محجوز",
    "Input Qty cannot be greater than available quantity": "لا يمكن أن تكون كمية الإدخال أكبر من الكمية المتاحة",
    "Output quantity cannot be greater than input quantity": "لا يمكن أن تكون كمية الإخراج أكبر من كمية الإدخال",
    "At least one operation is required.": "يجب إضافة عملية واحدة على الأقل.",
    "At least one batch is required.": "يجب إضافة دفعة واحدة على الأقل.",
    "Operation": "العملية",
    "Operations": "العمليات",
    "Status": "الحالة",
    "Approval Status": "حالة الموافقة",
    "Variance Status": "حالة الفروقات",
    "Process Cost": "تكلفة المعالجة",
    "Process Cost Total": "إجمالي تكلفة المعالجة",
    "Input Qty Total": "إجمالي كمية الإدخال",
    "Output Qty Total": "إجمالي كمية الإخراج",
    "Loss Qty": "كمية الفاقد",
    "Loss": "فاقد",
    "Quantity": "الكمية",
    "Total": "الإجمالي",
    "Profit": "الربح",
    "Purchase": "شراء",
    "Supplier": "المورد",
    "Location": "الموقع",
    "City": "المدينة",
    "Region": "المنطقة",
    "Country": "الدولة",
    "Elevation": "الارتفاع",
    "Notes": "ملاحظات",
    "Description": "الوصف",
    "Code": "الرمز",
    "Capacity": "السعة",
    "Capacity KG": "السعة بالكجم",
    "Current Qty": "الكمية الحالية",
    "Current Process Order": "أمر المعالجة الحالي",
    "Occupied Since": "مشغول منذ",
    "Last Cleaned On": "آخر تاريخ تنظيف",
    "Bed Type": "نوع السرير",
    "Barrel": "برميل",
    "Bed": "سرير تجفيف",
    "Resource": "مورد تشغيلي",
    "Resources": "الموارد التشغيلية",

    # DocType labels shown to users.
    "Coffee Batch": "دفعة بن",
    "Coffee Blend Order": "أمر خلط البن",
    "Coffee Cupping": "تقييم البن",
    "Coffee Drying Order": "أمر تجفيف البن",
    "Coffee Fermentation Order": "أمر تخمير البن",
    "Coffee Grading Order": "أمر تصنيف البن",
    "Coffee Packaging Order": "أمر تعبئة البن",
    "Coffee Peeling Service": "خدمة تقشير البن",
    "Coffee Process Order": "أمر معالجة البن",
    "Coffee Process Trial": "تجربة معالجة البن",
    "Coffee Production Plan": "خطة إنتاج البن",
    "Coffee Receiving Order": "أمر استلام البن",
    "Coffee Sorting Order": "أمر فرز البن",
    "Coffee Storage Unit": "وحدة تخزين البن",
    "Coffee Fermentation Barrel": "برميل تخمير البن",
    "Coffee Drying Bed": "سرير تجفيف البن",
    "Coffee Process Route": "مسار معالجة البن",
    "Coffee Process Route Step": "خطوة مسار معالجة البن",
    "Supplier Region": "منطقة المورد",

    # Navigation.
    "About": "حول",
    "Documentation": "التوثيق",
    "Frappe School": "مدرسة Frappe",
    "Frappe Support": "دعم Frappe",
    "Keyboard Shortcuts": "اختصارات لوحة المفاتيح",
    "My Profile": "ملفي الشخصي",
    "My Settings": "إعداداتي",
    "Reload": "إعادة تحميل",
    "Report an Issue": "الإبلاغ عن مشكلة",
    "Session Defaults": "الإعدادات الافتراضية للجلسة",
    "Toggle Full Width": "تبديل العرض الكامل",
    "Toggle Theme": "تبديل المظهر",
    "User Forum": "منتدى المستخدمين",
    "View Website": "عرض الموقع",

    # Common validation messages.
    "Please enter a value": "يرجى إدخال قيمة",
    "Please select": "يرجى الاختيار",
    "Please select a company": "يرجى اختيار الشركة",
    "Please select an item": "يرجى اختيار الصنف",
    "Please select a batch": "يرجى اختيار الدفعة",
    "Please select an operation": "يرجى اختيار العملية",
    "Invalid quantity": "الكمية غير صحيحة",
    "Invalid date": "التاريخ غير صحيح",
    "Not Found": "غير موجود",
    "Permission Error": "خطأ في الصلاحيات",
    "Error": "خطأ",
    "Warning": "تحذير",
    "Success": "نجاح",
    "Save": "حفظ",
    "Cancel": "إلغاء",
    "Submit": "اعتماد",
    "Close": "إغلاق",
    "Delete": "حذف",
    "Edit": "تعديل",
    "View": "عرض",
}


def is_arabic(text):
    return bool(re.search(r"[\u0600-\u06ff]", text or ""))


def run():
    app = "coffee_processing"
    messages = get_messages_for_app(app)

    translations = {}

    # Preserve any existing translations first.
    output = frappe.get_app_path(app, "translations", "ar.csv")
    if os.path.exists(output):
        with open(output, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 2 and row[0] and row[1]:
                    translations[row[0]] = row[1]

    # Apply curated translations only to extracted messages.
    for item in messages:
        source = item[1] if len(item) >= 2 else ""
        if not source:
            continue

        if is_arabic(source):
            continue

        if source in TRANSLATIONS:
            translations[source] = TRANSLATIONS[source]

    os.makedirs(os.path.dirname(output), exist_ok=True)

    # Frappe translation CSV has NO header.
    # Format: source,target
    rows = []
    extracted_sources = set()

    for item in messages:
        source = item[1] if len(item) >= 2 else ""
        if not source or is_arabic(source):
            continue

        extracted_sources.add(source)

        target = translations.get(source)
        if target:
            rows.append((source, target))

    rows.sort(key=lambda x: x[0].lower())

    with open(output, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        for source, target in rows:
            writer.writerow([source, target])

    untranslated = sorted(
        source
        for source in extracted_sources
        if source not in translations
    )

    print("=" * 70)
    print("COFFEE PROCESSING ARABIC TRANSLATION BUILD")
    print("=" * 70)
    print("Extracted messages :", len(messages))
    print("English/UI sources :", len(extracted_sources))
    print("Translated entries :", len(rows))
    print("Untranslated       :", len(untranslated))
    print("Translation file   :", output)
    print("=" * 70)

    if untranslated:
        print("UNTRANSLATED SOURCES:")
        for source in untranslated:
            print(" -", source)

    return {
        "messages": len(messages),
        "english_sources": len(extracted_sources),
        "translated": len(rows),
        "untranslated": len(untranslated),
        "file": output,
    }
