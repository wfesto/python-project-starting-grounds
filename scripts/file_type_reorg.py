import os
import shutil
import tkinter as tk
from tkinter import filedialog
import zipfile
import tarfile
import rarfile
import gzip
import bz2
import lzma

def get_directory():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    directory = filedialog.askdirectory(title="Select Input Directory, ya legend!")
    return directory

def categorize_file(extension):
    images = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    videos = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg'}
    audios = {'.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a'}
    archives = {'.zip', '.rar', '.tar', '.gz', '.7z', '.bz2'}
    
    ext = extension.lower()
    if ext in images:
        return 'images'
    elif ext in videos:
        return 'video'
    elif ext in audios:
        return 'audio'
    elif ext in archives:
        return 'archive'
    else:
        return 'other'

def extract_archive(archive_path, extract_dir, category_dirs, other_extensions):
    _, ext = os.path.splitext(archive_path)
    ext = ext.lower()
    success = False
    errors = []

    try:
        os.makedirs(extract_dir, exist_ok=True)
        if ext == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(extract_dir)
            success = True
        elif ext == '.rar':
            with rarfile.RarFile(archive_path, 'r') as rf:
                rf.extractall(extract_dir)
            success = True
        elif ext == '.tar':
            with tarfile.open(archive_path, 'r') as tf:
                tf.extractall(extract_dir)
            success = True
        elif ext == '.gz':
            if tarfile.is_tarfile(archive_path):  # Handle .tar.gz
                with tarfile.open(archive_path, 'r:gz') as tf:
                    tf.extractall(extract_dir)
            else:  # Handle single .gz file
                with gzip.open(archive_path, 'rb') as gf:
                    output_path = os.path.join(extract_dir, os.path.basename(archive_path)[:-3])
                    with open(output_path, 'wb') as f:
                        f.write(gf.read())
            success = True
        elif ext == '.bz2':
            if tarfile.is_tarfile(archive_path):  # Handle .tar.bz2
                with tarfile.open(archive_path, 'r:bz2') as tf:
                    tf.extractall(extract_dir)
            else:  # Handle single .bz2 file
                with bz2.open(archive_path, 'rb') as bf:
                    output_path = os.path.join(extract_dir, os.path.basename(archive_path)[:-4])
                    with open(output_path, 'wb') as f:
                        f.write(bf.read())
            success = True
        elif ext == '.7z':
            with lzma.open(archive_path, 'rb') as lzf:
                output_path = os.path.join(extract_dir, os.path.basename(archive_path)[:-3])
                with open(output_path, 'wb') as f:
                    f.write(lzf.read())
            success = True
    except Exception as e:
        errors.append(f"Error extracting {archive_path}: {str(e)}")
        success = False

    if success:
        # Process extracted files
        for root, _, files in os.walk(extract_dir):
            for file in files:
                file_path = os.path.join(root, file)
                _, new_ext = os.path.splitext(file)
                if not new_ext:
                    continue
                category = categorize_file(new_ext)
                if category == 'other' and new_ext:
                    other_extensions.add(new_ext.lower())

                if category not in category_dirs:
                    category_dirs[category] = os.path.join(input_dir, category)
                    os.makedirs(category_dirs[category], exist_ok=True)

                dest_dir = category_dirs[category]
                dest_path = os.path.join(dest_dir, file)
                if os.path.exists(dest_path):
                    base, new_ext = os.path.splitext(file)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(dest_dir, f"{base}_{counter}{new_ext}")
                        counter += 1

                try:
                    shutil.move(file_path, dest_path)
                except Exception as e:
                    errors.append(f"Error moving extracted file {file_path}: {str(e)}")

    return success, errors

def count_files_in_category_dirs(input_dir, categories):
    category_counts = {cat: 0 for cat in categories}
    other_extensions = set()

    for cat in categories:
        cat_dir = os.path.join(input_dir, cat)
        if os.path.exists(cat_dir):
            for _, _, files in os.walk(cat_dir):
                for file in files:
                    _, ext = os.path.splitext(file)
                    if ext and cat == 'other':
                        other_extensions.add(ext.lower())
                    category_counts[cat] += 1

    return category_counts, other_extensions

def organize_files(input_dir):
    categories = ['images', 'video', 'audio', 'archive', 'archive_extracted', 'other']
    category_dirs = {}
    errors = []

    # First pass: handle archives
    for root, _, files in os.walk(input_dir, topdown=False):
        if root == input_dir:
            continue
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            if not ext:
                continue
            if categorize_file(ext) == 'archive':
                extract_dir = os.path.join(input_dir, 'temp_extract')
                other_extensions = set()  # Temporary for archive extraction
                success, extract_errors = extract_archive(file_path, extract_dir, category_dirs, other_extensions)
                errors.extend(extract_errors)
                
                target_dir = 'archive_extracted' if success else 'archive'
                if target_dir not in category_dirs:
                    category_dirs[target_dir] = os.path.join(input_dir, target_dir)
                    os.makedirs(category_dirs[target_dir], exist_ok=True)
                
                dest_path = os.path.join(category_dirs[target_dir], file)
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(file)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(category_dirs[target_dir], f"{base}_{counter}{ext}")
                        counter += 1
                
                try:
                    shutil.move(file_path, dest_path)
                except Exception as e:
                    errors.append(f"Error moving archive {file_path}: {str(e)}")

    # Clean up temp extract folder
    temp_extract = os.path.join(input_dir, 'temp_extract')
    if os.path.exists(temp_extract):
        try:
            shutil.rmtree(temp_extract)
        except Exception as e:
            errors.append(f"Error removing temp extract folder: {str(e)}")

    # Second pass: handle non-archive files
    for root, _, files in os.walk(input_dir, topdown=False):
        if root == input_dir:
            continue
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            if not ext:
                continue
            category = categorize_file(ext)
            if category == 'archive':
                continue  # Already handled

            if category not in category_dirs:
                category_dirs[category] = os.path.join(input_dir, category)
                os.makedirs(category_dirs[category], exist_ok=True)

            dest_dir = category_dirs[category]
            dest_path = os.path.join(dest_dir, file)
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(file)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
                    counter += 1

            try:
                shutil.move(file_path, dest_path)
            except Exception as e:
                errors.append(f"Error moving {file_path}: {str(e)}")

    # Delete empty subdirectories
    non_empty_dirs = []
    for root, dirs, files in os.walk(input_dir, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if dir_path in category_dirs.values():
                continue
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                else:
                    non_empty_dirs.append(dir_path)
            except Exception as e:
                errors.append(f"Error deleting {dir_path}: {str(e)}")

    # Count files in category directories
    category_counts, other_extensions = count_files_in_category_dirs(input_dir, categories)

    # Output errors
    if errors:
        print("Whoops, hit some snags, love:")
        for err in errors:
            print(err)

    # Output category counts
    print("\nFile counts by category, you ripper:")
    for cat, count in category_counts.items():
        if count > 0:
            print(f"{cat.capitalize()}: {count}")

    # Output extensions in 'other' category
    if other_extensions:
        print("\nExtensions in 'other' category:")
        for ext in sorted(other_extensions):
            print(ext)

    # Output non-empty directories
    if non_empty_dirs:
        print("\nThese subdirs weren't empty, so I left 'em be:")
        for d in non_empty_dirs:
            print(d)
    else:
        print("\nAll subdirs cleaned up, nice and tidy!")

if __name__ == "__main__":
    input_dir = get_directory()
    if input_dir:
        print(f"Sortin' out {input_dir} for ya, cheeky one!")
        organize_files(input_dir)
    else:
        print("No directory picked? Aw, come on, let's try again!")