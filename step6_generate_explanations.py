import pandas as pd
import os
import re
from dotenv import load_dotenv
from groq import Groq
from tqdm import tqdm

# ==============================
# LOAD GROQ API
# ==============================

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# ==============================
# REMOVE PARENT CONTROLS
# ==============================

def remove_parent_controls(df):

    return df[
        df["ECC id control"]
        .astype(str)
        .str.count(r"\.") >= 2
    ]

# ==============================
# CLEAN AI OUTPUT
# ==============================

def clean_text(text):

    if not isinstance(text, str):
        return ""

    text = text.replace("Commonality:", "")
    text = text.replace("Justification:", "")
    text = text.replace("Differences:", "")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==============================
# GENERATE USING GROQ
# ==============================

def generate_text(ecc_text, nist_text):

    prompt = f"""
You are a cybersecurity ontology expert.

Compare these two cybersecurity controls.

ECC Control:
{ecc_text}

NIST Control:
{nist_text}

Generate:
Commonality
Justification
Differences

Rules:
- Keep answers concise and professional
- Focus only on cybersecurity meaning
- Do not mention scores
- Avoid repetition
- Differences must explain different focus areas
- Maximum 2 sentences each

Return ONLY in this format:

Commonality: ...
Justification: ...
Differences: ...
"""

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )

        output = response.choices[0].message.content.strip()

        commonality = ""
        justification = ""
        differences = ""

        lines = output.split("\n")

        for line in lines:

            line = line.strip()

            if line.startswith("Commonality:"):
                commonality = clean_text(
                    line.replace("Commonality:", "")
                )

            elif line.startswith("Justification:"):
                justification = clean_text(
                    line.replace("Justification:", "")
                )

            elif line.startswith("Differences:"):
                differences = clean_text(
                    line.replace("Differences:", "")
                )

        return commonality, justification, differences

    except Exception as e:

        print(f"GROQ ERROR: {e}")

        return (
            "Both controls share related cybersecurity objectives.",
            "The controls contain similar cybersecurity concepts.",
            "The controls differ in implementation focus and wording."
        )


# ==============================
# MAIN PROCESS
# ==============================

def run():

    input_path = "data/final_owl_ontology_refined_mappings.csv"
    output_path = "data/final_with_explanations.csv"

    df = pd.read_csv(input_path)

    # Remove parent controls
    df = remove_parent_controls(df)

    final_rows = []

    for _, row in tqdm(df.iterrows(), total=len(df)):

        new_row = {
            "ECC id control": row.get("ECC id control", ""),
            "Source Text": row.get("Source Text", "")
        }

        ecc_text = row.get("Source Text", "")

        for i in range(1, 11):

            suffix = f" {i}" if i > 1 else ""

            ref_col = f"NIST mapping{suffix}"
            text_col = f"Text{suffix}"

            dense_col = f"Dense{suffix}"
            sparse_col = f"Sparse{suffix}"
            hybrid_col = f"Hybrid{suffix}"

            ontology_col = f"Ontology score{suffix}"
            final_col = f"Final Score{suffix}"
            confidence_col = f"Confidence match{suffix}"

            if ref_col not in df.columns:
                continue

            nist_mapping = row.get(ref_col)

            if pd.isna(nist_mapping):
                continue

            nist_text = row.get(text_col, "")

            commonality, justification, differences = generate_text(
                ecc_text,
                nist_text
            )

            # ==============================
            # SAVE EVERYTHING TOGETHER
            # ==============================

            new_row.update({

                f"NIST mapping{suffix}":
                    nist_mapping,

                f"Text{suffix}":
                    nist_text,

                f"Dense{suffix}":
                    row.get(dense_col),

                f"Sparse{suffix}":
                    row.get(sparse_col),

                f"Hybrid{suffix}":
                    row.get(hybrid_col),

                f"Ontology score{suffix}":
                    row.get(ontology_col),

                f"Final Score{suffix}":
                    row.get(final_col),

                f"Confidence match{suffix}":
                    row.get(confidence_col),

                # ==============================
                # AI EXPLANATIONS
                # ==============================

                f"Commonality{suffix}":
                    commonality,

                f"Justification{suffix}":
                    justification,

                f"Differences{suffix}":
                    differences
            })

        final_rows.append(new_row)

    final_df = pd.DataFrame(final_rows)

    final_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nDone.")
    print(f"Saved to: {output_path}")


# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    run()