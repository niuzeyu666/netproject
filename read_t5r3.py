from docx import Document
doc = Document(r"C:\Users\lenovo\Desktop\3024244171_牛泽钰_第三周课程报告.docx")
t = doc.tables[5]
row = t.rows[3]
for j, cell in enumerate(row.cells):
    print(f"=== Col {j} ===")
    print(cell.text)
    print()
