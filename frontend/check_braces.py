with open('app/tools/[slug]/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('export default function ToolPage')
if start == -1:
    print('Function not found')
else:
    func_body = content[start:]
    print(f'Function body: open braces={func_body.count("{")}, close braces={func_body.count("}")}')
    
    import re
    for m in re.finditer(r'\};', func_body):
        line_num = func_body[:m.start()].count('\n') + 1
        print(f'  }; at function line {line_num}')