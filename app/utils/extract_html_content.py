import re


def extract_html_content(text: str, stack: str = "react-tailwind") -> str:
    """
    Extract code content from LLM response based on technology stack.

    Args:
        text: The raw text response from LLM
        stack: Technology stack ("react-tailwind", "html-tailwind", "svg")

    Returns:
        str: Extracted code content
    """
    # Remove markdown code blocks if present
    text = re.sub(r'```[\w]*\n|```', '', text)

    if stack == "svg":
        # Extract SVG content
        svg_match = re.search(r"(<svg.*?>.*?</svg>)", text, re.DOTALL)
        if svg_match:
            return svg_match.group(1)
    elif stack == "react-tailwind":
        # Extract React component content
        react_match = re.search(r"(export default function.*?})\s*$", text, re.DOTALL)
        if react_match:
            return react_match.group(1)
        # Alternative: look for const/function component definition
        alt_match = re.search(r"((?:const|function)\s+\w+\s*=?\s*(?:\([^)]*\))?\s*=>?\s*{.*?})\s*$", text, re.DOTALL)
        if alt_match:
            return alt_match.group(1)

    # Default: try to extract content within <html> tags
    html_match = re.search(r"(<html.*?>.*?</html>)", text, re.DOTALL)
    if html_match:
        return html_match.group(1)

    # If no specific patterns match, try to extract any HTML-like content
    body_match = re.search(r"(<body.*?>.*?</body>)", text, re.DOTALL)
    if body_match:
        return f"<html>\n{body_match.group(1)}\n</html>"

    div_match = re.search(r"(<div.*?>.*?</div>)", text, re.DOTALL)
    if div_match:
        return f"<html>\n<body>\n{div_match.group(1)}\n</body>\n</html>"

    # If no patterns match, clean up the text and return it
    cleaned_text = text.strip()
    print(f"[Code Extraction] No specific pattern found for stack '{stack}'. Raw content:\n{cleaned_text}")
    return cleaned_text


def clean_code_content(code: str) -> str:
    """
    Clean and format the extracted code content.

    Args:
        code: Raw code content

    Returns:
        str: Cleaned and formatted code
    """
    # Remove leading/trailing whitespace
    code = code.strip()

    # Remove extra blank lines
    code = re.sub(r'\n\s*\n', '\n\n', code)

    # Ensure proper indentation
    lines = code.split('\n')
    indent_level = 0
    formatted_lines = []

    for line in lines:
        # Adjust indent level based on brackets/braces
        stripped_line = line.strip()
        if stripped_line.endswith('{'):
            formatted_lines.append('  ' * indent_level + stripped_line)
            indent_level += 1
        elif stripped_line.startswith('}'):
            indent_level = max(0, indent_level - 1)
            formatted_lines.append('  ' * indent_level + stripped_line)
        else:
            formatted_lines.append('  ' * indent_level + stripped_line)

    return '\n'.join(formatted_lines)


def extract_code_content(text: str, stack: str = "react-tailwind") -> str:
    """
    Main function to extract and clean code content.

    Args:
        text: Raw text from LLM response
        stack: Technology stack being used

    Returns:
        str: Final cleaned and formatted code
    """
    # Extract the relevant code content
    extracted_content = extract_html_content(text, stack)

    # Clean and format the code
    cleaned_content = clean_code_content(extracted_content)

    return cleaned_content
