# Agent-Next-Web

A simple web interface for interacting with AI agents' code generation capabilities. This project draws inspiration from two excellent projects: [SWEAgent](https://github.com/SWE-agent/SWE-agent) and [OpenHands](https://github.com/All-Hands-AI/OpenHands)

## Requirements
* **python >= 3.12**
* **conda**

## Setup with Conda
1. Create and activate a new conda environment
   ```sh
   conda create -n agent python=3.12
   conda activate agent
   ```

2. Clone the repository
   ```sh
   git clone https://github.com/mannaandpoem/Agent-Next-Web.git
   cd Agent-Next-Web
   ```

3. Install requirements
   ```sh
   pip install -r requirements.txt
   ```

4. Configure your API keys in `config/config.yaml`

## Usage
Run the application:
```bash
python main.py
```

Then simply enter your prompts. Type 'exit' to quit.

## Example
```bash
Enter your prompt: write a simple calculator
...
Enter your prompt: exit
Goodbye!
```

## License
[MIT License](LICENSE)

## Acknowledgments
Special thanks to the teams behind SWEAgent and OpenHands for their pioneering work in AI-assisted software development, which helped shape this project.
