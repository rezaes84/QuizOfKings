Quiz of Kings Project ✨
The Ultimate Knowledge and Intelligence Battle! 🚀
Quiz of Kings is a competitive web-based platform where two players can challenge each other's knowledge across various categories. Developed using the Flask framework in Python, this project delivers a dynamic and engaging gaming experience.

🌟 Key Features
👥 User Management: Secure player registration, login, and session handling.

🎮 Gameplay System: A complete game flow with multiple rounds, real-time question display, score calculation, and winner determination.

🗄️ Robust Database Integration: Utilizes PostgreSQL to manage all game data, including players, questions, categories, and game sessions.

📜 Match History: Players can view a detailed history of their past matches, scores, and outcomes.

🏆 Leaderboards: A dynamic ranking system based on player experience points (XP) and win rates.

🛠️ Admin Panel: A dedicated administrative interface for moderating user-submitted questions and managing (blocking) user accounts.

💻 Technologies Used
Backend:

Python

Flask

Database:

PostgreSQL

psycopg2 (Database driver)

werkzeug.security (For password hashing)

⚙️ How to Run the Project
Follow these instructions to set up and run the project on your local machine.

Prerequisites
Make sure you have the following installed:

Python 3.x

PostgreSQL

1. Clone the Repository
git clone https://github.com/your-username/Quiz-of-Kings.git
cd Quiz-of-Kings

2. Set Up Virtual Environment and Dependencies
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
pip install -r requirements.txt

Note: If you don't have a requirements.txt file, you can install the dependencies manually:

pip install Flask psycopg2-binary

3. Configure the Database
Create a new PostgreSQL database named quiz_of_kings.

Open the app.py file and update the DATABASE_URL with your database credentials.

# In app.py
DATABASE_URL = "postgresql://<your_user>:<your_password>@localhost:5432/quiz_of_kings"

The necessary tables will be created automatically on the first run.

4. Run the Application
python app.py

You can then access the application in your browser at http://127.0.0.1:5000.

▶️ How to Play
Register & Log In: Create a new user account or log in with an existing one.

Find a Match: Wait for another player to join and start a game.

Start the Game: Select a category to begin the first round. The game continues until a winner is determined after multiple rounds.

Review Results: At the end of the game, you can view a detailed breakdown of the results. Your full match history is also available in your profile.
