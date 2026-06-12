#!/usr/bin/env python
import os
import sys
import re
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

def remove_hash_comment_lines(text):
    return '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))

def get_app_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def extract_mod_name_from_input_dir(input_dir):
    input_dir = Path(input_dir).resolve()
    mod_files = sorted(input_dir.glob('*.mod'))
    if not mod_files:
        print(f"警告: 输入目录中未找到 .mod 文件，已跳过 dependencies 更新: '{input_dir}'")
        return None
    for mod_file in mod_files:
        with open(mod_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        name_match = re.search(r'^\s*name\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if name_match:
            return name_match.group(1).strip()
    print(f"警告: 输入目录中的 .mod 文件未找到 name 字段，已跳过 dependencies 更新: '{input_dir}'")
    return None

def update_descriptor_dependencies(descriptor_file, dependency_name):
    descriptor_file = Path(descriptor_file).resolve()
    if not descriptor_file.exists():
        print(f"警告: 未找到 descriptor 文件，已跳过 dependencies 更新: '{descriptor_file}'")
        return False
    with open(descriptor_file, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    dep_block_match = re.search(r'dependencies\s*=\s*\{(?P<body>.*?)\}', content, re.DOTALL)
    if dep_block_match:
        dep_body = dep_block_match.group('body')
        existing_deps = [x.strip() for x in re.findall(r'"([^"]+)"', dep_body)]
        if dependency_name in existing_deps:
            return False
        
        indent_match = re.search(r'\n([ \t]+)"', dep_body)
        indent = indent_match.group(1) if indent_match else '    '
        
        if dep_body.strip():
            dep_body_new = dep_body
            if not dep_body_new.endswith('\n'):
                dep_body_new += '\n'
            dep_body_new += f'{indent}"{dependency_name}"\n'
        else:
            dep_body_new = f'\n{indent}"{dependency_name}"\n'
            
        content_new = content[:dep_block_match.start('body')] + dep_body_new + content[dep_block_match.end('body'):]
    else:
        content_new = content
        if not content_new.endswith('\n'):
            content_new += '\n'
        content_new += f'\ndependencies = {{\n    "{dependency_name}"\n}}\n'
        
    with open(descriptor_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content_new)
    return True

def extract_focus_ids_from_files(input_dir):
    ids = []
    focus_dir = Path(input_dir).resolve() / 'common' / 'national_focus'
    if not focus_dir.exists():
        return ids
    for root, _, files in os.walk(focus_dir):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = remove_hash_comment_lines(f.read())
                focus_blocks = re.findall(r'focus\s*=\s*\{([^}]*)\}', content, re.DOTALL)
                for block in focus_blocks:
                    id_match = re.search(r'id\s*=\s*([a-zA-Z0-9_\.]+)', block)
                    if id_match:
                        focus_id = id_match.group(1)
                        ids.append(focus_id)
    return list(dict.fromkeys(ids))

def extract_focus_from_target_file(target_file):
    focus_ids = []
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            content = remove_hash_comment_lines(f.read())
        focus_blocks = re.findall(r'focus\s*=\s*\{([^}]*)\}', content, re.DOTALL)
        for block in focus_blocks:
            lines = block.splitlines()
            stripped_lines = [line.strip() for line in lines if line.strip()]
            focus_ids.extend(stripped_lines)
        return focus_ids
    except Exception as e:
        print(f"错误: 读取目标文件失败: {e}", file=sys.stderr)
        return []

def merge_files(extracted_file, target_file, output_file):
    extracted_focus_ids = []
    with open(extracted_file, 'r', encoding='utf-8') as f:
        extracted_focus_ids = f.read().splitlines()
    target_focus_ids = extract_focus_from_target_file(target_file)
    combined_focus_ids = list(dict.fromkeys(extracted_focus_ids + target_focus_ids))
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(combined_focus_ids))

def dedup_and_sort(input_file, output_file):
    input_path = Path(input_file).resolve()
    if not input_path.exists():
        print(f"错误: 文件 '{input_file}' 不存在！", file=sys.stderr)
        return False
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    unique_lines = list(dict.fromkeys(line.rstrip('\n') for line in lines))
    sorted_lines = sorted(unique_lines, key=str.lower)
    with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
        for line in sorted_lines:
            f.write(line + '\n')
    return True

def generate_focus_effects(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        focus_ids = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    if not focus_ids:
        print('警告: 没有有效的 focus ID。')
        return False
        
    costs = [1, 2, 7, 35]
    output_lines = []
    
    for cost in costs:
        output_lines.append(f"apply_focus_cost_reduction_{cost} = {{")
        output_lines.append("    reduce_focus_completion_cost = {")
        output_lines.append("        focus = {")
        for fid in focus_ids:
            output_lines.append(f"            {fid}")
        output_lines.append("        }")
        output_lines.append(f"        cost = {cost}")
        output_lines.append("    }")
        output_lines.append("}\n")
        
    for cost in costs:
        output_lines.append(f"apply_focus_cost_increase_{cost} = {{")
        output_lines.append("    reduce_focus_completion_cost = {")
        output_lines.append("        focus = {")
        for fid in focus_ids:
            output_lines.append(f"            {fid}")
        output_lines.append("        }")
        output_lines.append(f"        cost = {-cost}")
        output_lines.append("    }")
        output_lines.append("}\n")
        
    with open(output_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(output_lines))
    return True

def run_pipeline(input_dir, output_dir, merge_file, descriptor_file):
    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir).resolve()
    merge_file = Path(merge_file).resolve()
    descriptor_file = Path(descriptor_file).resolve()
    
    common_dir = merge_file.parent.parent
    scripted_effects_dir = merge_file.parent
    
    if not common_dir.exists():
        print(f"错误: 必需目录不存在: '{common_dir}'", file=sys.stderr)
        return False
        
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        
    extracted_output = output_dir / 'extracted_focus_ids.txt'
    merged_output = output_dir / 'merged_focus_ids.txt'
    sorted_output = output_dir / 'sorted_focus_ids.txt'
    final_output = output_dir / 'final_generated_output.txt'
    
    try:
        extracted_ids = extract_focus_ids_from_files(input_dir)
        with open(extracted_output, 'w', encoding='utf-8') as f:
            f.write('\n'.join(extracted_ids))
            
        if merge_file.exists():
            merge_files(extracted_output, merge_file, merged_output)
        else:
            print(f"警告: '{merge_file}' 不存在，跳过合并步骤。")
            shutil.copyfile(extracted_output, merged_output)
            
        if not dedup_and_sort(merged_output, sorted_output):
            raise Exception('去重和排序失败')
            
        if not generate_focus_effects(sorted_output, final_output):
            raise Exception('生成最终文件失败')
            
        if not scripted_effects_dir.exists():
            scripted_effects_dir.mkdir(parents=True, exist_ok=True)
            
        shutil.copyfile(final_output, merge_file)
        
        dependency_name = extract_mod_name_from_input_dir(input_dir)
        if dependency_name:
            update_descriptor_dependencies(descriptor_file, dependency_name)
            
        if output_dir.exists():
            shutil.rmtree(output_dir)
            
        print('所有步骤成功完成！')
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def main():
    base_dir = get_app_base_dir()
    merge_file = base_dir / 'common' / 'scripted_effects' / 'adjust_focus_time_scripted_effects.txt'
    output_dir = base_dir / 'temp'
    descriptor_file = base_dir / 'descriptor.mod'
    
    if len(sys.argv) >= 2:
        input_dir = Path(sys.argv[1]).resolve()
        if not run_pipeline(input_dir, output_dir, merge_file, descriptor_file):
            sys.exit(1)
        return
        
    root = tk.Tk()
    root.withdraw()
    input_dir = filedialog.askdirectory(title='请选择 MOD 根目录')
    root.destroy()
    
    if not input_dir:
        return
        
    success = run_pipeline(input_dir, output_dir, merge_file, descriptor_file)
    if success:
        messagebox.showinfo('完成', '处理完成，已更新 scripted_effects 文件。')
    else:
        messagebox.showerror('失败', '处理失败，请在命令行运行 exe 查看详细错误。')
        sys.exit(1)

if __name__ == '__main__':
    main()
