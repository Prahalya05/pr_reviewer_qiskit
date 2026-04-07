import os
from openai import OpenAI
from dotenv import load_dotenv

def test_ollama():
    # Load environment variables from .env if present
    load_dotenv()
    
    # Get config from .env or use defaults
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    # You can change the model if you're using a different one
    model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    
    print(f"Connecting to Ollama at: {base_url}")
    print(f"Using model: {model}")
    print("-" * 40)
    
    try:
        # Initialize the OpenAI client pointing to the local Ollama instance
        client = OpenAI(
            base_url=base_url,
            # API key is required by the SDK but not actually checked by Ollama
            api_key="ollama", 
        )
        
        # Test prompt
        prompt = "Write a very short Python function to calculate the factorial of a number."
        print(f"Prompt: '{prompt}'\n")
        print("Waiting for response from the model...")
        
        # Make the request
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant. Be concise."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=150
        )
        
        print("\nResponse received:")
        print("-" * 40)
        print(response.choices[0].message.content)
        print("-" * 40)
        print("\n✅ Connection successful! The model is responding correctly.")
        
    except Exception as e:
        print("\n❌ Error connecting to Ollama:")
        print(e)
        print("\nPlease ensure that:")
        print("1. Ollama is running (you can start it with 'ollama serve' if it's not a background service)")
        print(f"2. The model '{model}' has been pulled ('ollama pull {model}')")

if __name__ == "__main__":
    test_ollama()
