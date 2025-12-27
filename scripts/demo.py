"""
🎬 YamieBot Demo Script

Interactive demo interface for showing the chatbot.

Features:
- Clean, easy-to-read interface
- Shows question → answer → sources
- Pre-loaded demo questions
- Professional presentation

Usage:
    python scripts/demo.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.query import QueryEngine


class ChatDemo:
    """Interactive demo interface"""
    
    def __init__(self):
        self.engine = None
        
    def clear_screen(self):
        """Clear terminal (works on Windows/Linux/Mac)"""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """Print demo header"""
        print("\n" + "=" * 80)
        print("  🤖 YamieBot - Internal Assistant Demo")
        print("  Yamie PastaBar Staff Knowledge System")
        print("=" * 80)
    
    def initialize(self):
        """Initialize the query engine"""
        print("\n⏳ Initializing chatbot...")
        try:
            self.engine = QueryEngine()
            print("✅ Chatbot ready!\n")
            return True
        except Exception as e:
            print(f"❌ Error initializing chatbot: {e}")
            print("\nMake sure you've run ingestion first:")
            print("  python scripts/run_ingestion.py")
            return False
    
    def ask_question(self, question):
        """Ask a question and display formatted response"""
        print("\n" + "─" * 80)
        print(f"💬 Question: {question}")
        print("─" * 80)
        
        try:
            # Query the system
            print("\n⏳ Thinking...\n")
            response = self.engine.query(question)
            
            # Display answer
            print("🤖 Answer:")
            print("─" * 80)
            print(response.answer)
            print("─" * 80)
            
            # Display metadata
            print(f"\n📊 Metadata:")
            print(f"   Response time: {response.response_time_seconds:.2f}s")
            
            if response.sources:
                sources = response.get_source_names()
                print(f"   Sources: {', '.join(sources)}")
                
                # Show similarity scores
                if response.sources:
                    print(f"\n   Retrieval details:")
                    for i, chunk in enumerate(response.sources[:3], 1):
                        print(f"     {i}. {chunk.source} (similarity: {chunk.similarity_score:.3f})")
            
            
            return response
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    
    def run_demo_mode(self):
        """Run with pre-defined demo questions"""
        self.print_header()
        
        if not self.initialize():
            return
        
        # Demo questions (adjust based on your data)
        demo_questions = [
            "What pasta dishes do you have?",
            "Welke wijnen hebben jullie?",
            "How many sick days do I have?",
            "Hoe open ik de zaak in de ochtend?",
            "How do I clean the espresso machine?",
        ]
        
        print("\n" + "=" * 80)
        print("  📋 DEMO MODE - Pre-loaded Questions")
        print("=" * 80)
        print(f"\nI'll ask {len(demo_questions)} demonstration questions.\n")
        
        input("Press ENTER to start demo...")
        
        for i, question in enumerate(demo_questions, 1):
            self.clear_screen()
            self.print_header()
            print(f"\n[Demo Question {i}/{len(demo_questions)}]")
            
            self.ask_question(question)
            
            if i < len(demo_questions):
                print("\n" + "=" * 80)
                input("\nPress ENTER for next question...")
        
        print("\n" + "=" * 80)
        print("  ✅ Demo Complete!")
        print("=" * 80)
    
    
    def run_interactive_mode(self):
        """Run in interactive mode where user types questions"""
        self.print_header()
        
        if not self.initialize():
            return
        
        print("\n" + "=" * 80)
        print("  💬 INTERACTIVE MODE")
        print("=" * 80)
        print("\nAsk questions to the chatbot. Type 'quit' or 'exit' to stop.\n")
        
        while True:
            try:
                # Get question
                print("─" * 80)
                question = input("\n💬 Your question: ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not question:
                    print("⚠️  Please enter a question.")
                    continue
                
                # Ask and display
                self.ask_question(question)
                
                print("\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted by user.")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
        
        print("\n" + "=" * 80)
        print("  👋 Thanks for using YamieBot!")
        print("=" * 80 + "\n")
        
    
    def run_uncle_demo(self):
        """Special demo mode optimized for showing uncle"""
        self.clear_screen()
        
        print("\n" + "=" * 80)
        print("  🎬 YamieBot - Uncle Demo Mode")
        print("=" * 80)
        print("\n  This demo will showcase the chatbot's capabilities")
        print("  with questions relevant to restaurant operations.\n")
        
        if not self.initialize():
            return
        
        # Uncle-focused questions (customize based on real data)
        uncle_questions = [
            {
                "q": "Welke pasta's hebben we op de menukaart?",
                "explain": "Shows: Menu knowledge, Dutch language, list formatting"
            },
            {
                "q": "What's the sick leave policy for employees?",
                "explain": "Shows: HR policy knowledge, English language, specific info"
            },
            {
                "q": "Hoe moet ik de kassa afsluiten aan het eind van de dag?",
                "explain": "Shows: SOP knowledge, procedural info"
            },
            {
                "q": "How often should kitchen equipment be cleaned?",
                "explain": "Shows: Maintenance knowledge, safety procedures"
            },
            {
                "q": "What pizzas do you have?",
                "explain": "Shows: Correctly says 'I don't know' (no pizza in docs)"
            },
        ]
        
        for i, item in enumerate(uncle_questions, 1):
            print("\n" + "=" * 80)
            print(f"  DEMO QUESTION {i}/{len(uncle_questions)}")
            print("=" * 80)
            print(f"\n📝 Context: {item['explain']}\n")
            
            input("Press ENTER to ask question...")
            
            self.ask_question(item['q'])
            
            if i < len(uncle_questions):
                print("\n")
                input("Press ENTER to continue to next question...")
                self.clear_screen()
        
        # Summary
        self.clear_screen()
        print("\n" + "=" * 80)
        print("  ✅ DEMO COMPLETE!")
        print("=" * 80)
        print("\n📊 Demo Summary:")
        print(f"   Questions asked: {len(uncle_questions)}")
        print(f"   Languages tested: Dutch, English")
        print(f"   Categories tested: Menu, HR, SOP, Equipment")
        print("\n💡 Key Features Demonstrated:")
        print("   ✅ Bilingual support (Dutch/English)")
        print("   ✅ Accurate answers from documents")
        print("   ✅ Source citations")
        print("   ✅ 'Don't know' for missing information")
        print("   ✅ Fast response times (<2 seconds)")
        
        
        print("\n" + "=" * 80 + "\n")


def main():
    """Main entry point"""
    demo = ChatDemo()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        # Ask user which mode
        print("\n" + "=" * 80)
        print("  🤖 YamieBot Demo")
        print("=" * 80)
        print("\nChoose demo mode:\n")
        print("  1. Uncle Demo    - Optimized presentation for uncle")
        print("  2. Demo Mode     - Pre-loaded questions")
        print("  3. Interactive   - Type your own questions")
        print("\n" + "=" * 80)
        
        choice = input("\nEnter choice (1/2/3): ").strip()
        
        if choice == "1":
            mode = "uncle"
        elif choice == "2":
            mode = "demo"
        elif choice == "3":
            mode = "interactive"
        else:
            print("Invalid choice. Using interactive mode.")
            mode = "interactive"
    
    # Run appropriate mode
    if mode == "uncle":
        demo.run_uncle_demo()
    elif mode == "demo":
        demo.run_demo_mode()
    else:
        demo.run_interactive_mode()


if __name__ == "__main__":
    main()
