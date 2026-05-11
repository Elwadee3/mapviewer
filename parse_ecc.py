import re
import csv
import pdfplumber

PDF_PATH = "ECC.pdf"
OUTPUT_PATH = "ecc_parsed.csv"

DOMAINS = {
    '1': 'Cybersecurity Governance',
    '2': 'Cybersecurity Defense',
    '3': 'Cybersecurity Resilience',
    '4': 'Third-Party and Cloud Computing Cybersecurity'
}

SUBDOMAINS = {
    '1.1': 'Cybersecurity Strategy',
    '1.2': 'Cybersecurity Management',
    '1.3': 'Cybersecurity Policies and Procedures',
    '1.4': 'Cybersecurity Roles and Responsibilities',
    '1.5': 'Cybersecurity Risk Management',
    '1.6': 'Cybersecurity in Information and Technology Project Management',
    '1.7': 'Compliance with Cybersecurity Standards, Laws and Regulations',
    '1.8': 'Periodical Cybersecurity Review and Audit',
    '1.9': 'Cybersecurity in Human Resources',
    '1.10': 'Cybersecurity Awareness and Training Program',
    '2.1': 'Asset Management',
    '2.2': 'Identity and Access Management',
    '2.3': 'Information System and Information Processing Facilities Protection',
    '2.4': 'Email Protection',
    '2.5': 'Network Security',
    '2.6': 'Mobile Devices Security',
    '2.7': 'Data and Information Protection',
    '2.8': 'Cryptography',
    '2.9': 'Backup and Recovery Management',
    '2.10': 'Vulnerabilities Management',
    '2.11': 'Penetration Testing',
    '2.12': 'Cybersecurity Event Logs and Monitoring Management',
    '2.13': 'Cybersecurity Incident and Threat Management',
    '2.14': 'Physical Security',
    '2.15': 'Web Application Security',
    '3.1': 'Cybersecurity Resilience Aspects of Business Continuity Management (BCM)',
    '4.1': 'Third-Party Cybersecurity',
    '4.2': 'Cloud Computing and Hosting Cybersecurity'
}


def extract_text(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    return text


def clean(text):
    if not text:
        return ""
    text = re.sub(r'د وﺪحﻣ - ﺪﻴﻘﻣ', '', text)
    text = re.sub(r'دودحم - ديقم', '', text)
    text = re.sub(r'Essential Cybersecurity Controls', '', text)
    text = re.sub(r'Document classification: Public TLP: White', '', text)
    text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n+', ' ', text)
    return text.strip()


def normalize_ref(ref):
    return ref.replace('-', '.')


def get_context(ref):
    parts = ref.split('.')
    ctx = []
    if parts[0] in DOMAINS:
        ctx.append(DOMAINS[parts[0]])
    if len(parts) >= 2:
        sub = f"{parts[0]}.{parts[1]}"
        if sub in SUBDOMAINS:
            ctx.append(SUBDOMAINS[sub])
    return " : ".join(ctx)


def parse_controls(text):
    text = re.sub(r'\d+\nDocument classification[^\n]*\n[^\n]*\n\n[^\n]*\nEssential Cybersecurity Controls', '\n', text)
    text = re.sub(r'Essential Cybersecurity Controls[^\n]*', '', text)
    text = re.sub(r'Document classification[^\n]*', '', text)
    text = re.sub(r'The Essential Cybersecurity Controls \(ECC\)', '', text)
    text = re.sub(r'Details of the Essential Cybersecurity Controls \(ECC\)', '', text)
    text = re.sub(r'د وﺪحﻣ - ﺪﻴﻘﻣ', '', text)
    text = re.sub(r'دودحم - ديقم', '', text)
    text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\d\s+[A-Z][a-zA-Z\s]+(?=\n)', '', text)
    text = re.sub(r'\n\d-\d+\s+[A-Z][a-zA-Z\s()]+(?=\n)', '', text)
    text = re.sub(r'Objective[^\n]*', '', text)
    text = re.sub(r'\nControls\n', '\n', text)
    text = re.sub(r'To ensure[^\n]+\n', '', text)
    
    ref_pattern = re.compile(r'(\d-\d+-\d+|\d+\.\d+\.\d+\.\d+)')
    matches = list(ref_pattern.finditer(text))
    controls = {}
    
    for i, m in enumerate(matches):
        ref = normalize_ref(m.group(1))
        
        if i + 1 < len(matches):
            after_end = matches[i + 1].start()
        else:
            after_end = len(text)
        
        after_text = text[m.end():after_end]
        sent_end = re.search(r'\.\s*\n', after_text)
        if sent_end:
            continuation = after_text[:sent_end.end()].strip()
        else:
            continuation = after_text.strip()
        
        if i > 0:
            prev_end = matches[i - 1].end()
            between = text[prev_end:m.start()]
            last_sent = between.rfind('.\n')
            if last_sent > 0:
                before_text = between[last_sent + 2:].strip()
            else:
                last_sent = re.search(r'\.\s+(?=[A-Z])', between)
                if last_sent:
                    before_text = between[last_sent.end():].strip()
                else:
                    before_text = between.strip()
        else:
            before_text = text[:m.start()].strip()
            ctrl_pos = before_text.rfind('Controls')
            if ctrl_pos > 0:
                before_text = before_text[ctrl_pos + 8:].strip()
        
        ctrl_text = before_text + " " + continuation
        ctrl_text = re.sub(r'\s+', ' ', ctrl_text).strip()
        
        if ctrl_text and len(ctrl_text) > 15:
            ctx = get_context(ref)
            full = f"{ctx} : {ctrl_text}" if ctx else ctrl_text
            controls[ref] = full
    
    # Handle parent controls with sub-items
    all_refs = set(controls.keys())
    parent_refs = set()
    for ref in all_refs:
        parts = ref.split('.')
        if len(parts) == 4:
            parent = '.'.join(parts[:3])
            parent_refs.add(parent)
    
    for parent in parent_refs:
        first_sub = f"{parent}.1"
        first_sub_pos = text.find(first_sub)
        if first_sub_pos < 0:
            continue
        
        search_start = max(0, first_sub_pos - 600)
        before_text = text[search_start:first_sub_pos]
        
        colon_match = re.search(r'([A-Z][^.]*(?:minimum|following|includes?):\s*)$', before_text, re.IGNORECASE)
        if not colon_match:
            colon_match = re.search(r'([A-Z][^.]*:\s*)$', before_text)
        
        if colon_match:
            intro = colon_match.group(1).strip()
            pre_colon = before_text[:colon_match.start()]
            last_sent = re.search(r'\.\s*\n', pre_colon[::-1])
            if last_sent:
                last_period = len(pre_colon) - last_sent.end()
                intro = pre_colon[last_period:].strip() + " " + intro
            else:
                last_period = pre_colon.rfind('.')
                if last_period > 0:
                    intro = pre_colon[last_period+1:].strip() + " " + intro
            
            intro = re.sub(r'\s+', ' ', intro).strip()
            if intro and len(intro) > 20:
                ctx = get_context(parent)
                full = f"{ctx} : {intro}" if ctx else intro
                controls[parent] = full
    
    # Prepend parent intro to sub-controls
    for ref in list(controls.keys()):
        parts = ref.split('.')
        if len(parts) == 4:
            parent = '.'.join(parts[:3])
            if parent in controls:
                parent_text = controls[parent]
                if ' : ' in parent_text:
                    intro_parts = parent_text.split(' : ')
                    if len(intro_parts) >= 3:
                        intro = intro_parts[-1]
                        sub_text = controls[ref]
                        if intro not in sub_text:
                            sub_parts = sub_text.split(' : ')
                            if len(sub_parts) >= 2:
                                if len(sub_parts) >= 3:
                                    context = ' : '.join(sub_parts[:-1])
                                    content = sub_parts[-1]
                                else:
                                    context = sub_parts[0]
                                    content = sub_parts[-1]
                                controls[ref] = f"{context} : {intro} : {content}"
    
    return [{'control_ref': ref, 'control_text': txt} for ref, txt in controls.items()]


def sort_controls(controls):
    def key(c):
        parts = [int(p) for p in c['control_ref'].split('.') if p.isdigit()]
        return tuple(parts + [0] * (5 - len(parts)))
    return sorted(controls, key=key)


def parse_pdf(pdf_path):
    text = extract_text(pdf_path)
    controls = parse_controls(text)
    controls = sort_controls(controls)
    return controls


def main():
    print(f"Parsing {PDF_PATH}...")
    controls = parse_pdf(PDF_PATH)
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['control_ref', 'control_text'])
        writer.writeheader()
        writer.writerows(controls)
    print(f"Saved {len(controls)} controls to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
