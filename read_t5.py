from docx import Document
doc = Document(r"C:\Users\lenovo\Desktop\3024244171_牛泽钰_第三周课程报告.docx")
t = doc.tables[5]
for i, row in enumerate(t.rows):
    cells = [c.text[:60] for c in row.cells]
    print(f"Row {i}: {cells}")
