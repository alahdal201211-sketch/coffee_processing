# Coffee Processing — النسخة المكتملة المبنية على النسخة الأصلية

هذه الحزمة مبنية فوق `coffee_processing(2).zip` مع الحفاظ على ملفات الـDashboard والـWorkspace الأصلية.

## التثبيت

```bash
cd /workspace/development/frappe-bench
cp -a apps/coffee_processing apps/coffee_processing_backup_$(date +%Y%m%d_%H%M%S)
rm -rf apps/coffee_processing
unzip -q /path/to/coffee_processing_FINAL_ORIGINAL_BASED.zip -d /tmp/coffee_final
cp -a /tmp/coffee_final/coffee_processing apps/coffee_processing
bench --site YOUR_SITE migrate
bench build --app coffee_processing
bench --site YOUR_SITE clear-cache
bench --site YOUR_SITE clear-website-cache
```

## الاختبار الساكن قبل تشغيل Bench

```bash
python3 apps/coffee_processing/scripts/validate_package.py
```

## اختبار Master Data من Console

```bash
bench --site YOUR_SITE console
```

```python
from coffee_processing.setup.install import install_master_data
install_master_data()
print('YER/SAR/USD:', [x for x in ['YER','SAR','USD'] if frappe.db.exists('Currency', x)])
print('Items:', frappe.db.count('Item'))
print('Warehouses:', frappe.db.count('Warehouse', {'company':'الاهدل للبن'}))
print('Cost Centers:', frappe.db.count('Cost Center', {'company':'الاهدل للبن'}))
print('Operations:', frappe.get_all('Coffee Operation Master', pluck='name'))
print('Routes:', frappe.get_all('Coffee Process Route', pluck='name'))
```

## اختبار دورة حقيقية

1. أنشئ Purchase Receipt بالعملة YER.
2. أنشئ Coffee Batch للاستلام الواحد أو مجموعة الاستلامات.
3. أنشئ Coffee Process Order لكل مرحلة.
4. اختبر المدخلات والمخرجات والفاقد والتكلفة.
5. اختبر التقشير بقيمة ثم بالنسبة في حالتين منفصلتين.
6. اختبر Trial ثم Real.
7. نفذ Payment Entry للمورد/العميل بعملة SAR ثم USD مع Exchange Rate حقيقي.
8. راجع Stock Ledger وGL Entry وBatch وCost Center.
9. نفذ عملية بيع ثم راجع ربحية الـBatch.

> لا توجد أسعار صرف SAR/USD افتراضية في الحزمة؛ يجب إدخال سعر الصرف الفعلي حسب تاريخ الحركة.
