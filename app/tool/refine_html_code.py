from typing import Dict, Any

from app.tool.base import BaseTool
from app.tool.oh_editor import OHEditor


class RefineHTMLCode(BaseTool):
    name: str = "refine_html_code"
    description: str = """Advanced HTML code optimization tool that performs quality-focused refinements based on the following criteria:

1. Semantic HTML: Use appropriate HTML tags to convey meaning.
2. Accessibility: Ensure content is usable for all, including those with disabilities.
3. Clean and Readable Code: Maintain consistent formatting and meaningful naming conventions.
4. Responsive Design: Implement designs that adapt to various screen sizes.
5. Performance Optimization: Minimize file sizes and optimize selectors for faster loading.
6. Cross-Browser Compatibility: Ensure consistent rendering across different browsers.
7. Validation: Use W3C validators to check for errors and deprecated elements.
8. Maintainability: Structure code for easy updates and modifications.
9. Use of Best Practices: Avoid anti-patterns like excessive specificity and inline styles.
10. Documentation: Provide clear documentation for styles and design choices.

The tool performs surgical edits to improve existing HTML implementations while:
- Identifying exact code segments for replacement
- Maintaining original functionality while optimizing
- Focusing on complexity enhancement and quality improvements"""

    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to target HTML file (e.g. '/workspace/index.html')"
            },
            "old_str": {
                "type": "string",
                "description": "EXACT HTML code segment to replace (include full line(s) with original indentation)"
            },
            "new_str": {
                "type": "string",
                "description": "Optimized replacement HTML code that must:\n1. Improve semantic structure\n2. Enhance accessibility\n3. Maintain responsive design\n4. Follow best practices"
            }
        },
        "required": ["path", "old_str", "new_str"]
    }
    editor: OHEditor = OHEditor()

    async def execute(self, **kwargs) -> str:
        path = kwargs.get("path", "")
        old_str = kwargs.get("old_str", "")
        new_str = kwargs.get("new_str", "")

        if not path.strip():
            raise ValueError("Target HTML file path required")
        if not old_str.strip():
            raise ValueError("Original HTML segment required for replacement")
        if not new_str.strip():
            raise ValueError("Optimized replacement HTML code required")

        # Replace old HTML code with refined implementation
        result = await self.editor.execute(
            command="str_replace",
            path=path,
            old_str=old_str,
            new_str=new_str
        )

        return result
