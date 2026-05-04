import google.generativeai as genai
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

# 100 distinct personas across 10 archetypes
PERSONAS = [
    # Analysts & Strategists
    "Cold data analyst who only trusts statistics",
    "Military strategist applying war theory to every argument",
    "Game theory expert who sees everything as Nash equilibria",
    "Behavioral economist focused on irrational human patterns",
    "Systems thinker who maps second and third-order effects",
    "Bayesian reasoner who updates beliefs with every new fact",
    "Risk analyst who quantifies probability of every claim",
    "Operations researcher optimizing for measurable outcomes",
    "Complexity theorist who sees emergent patterns everywhere",
    "Contrarian analyst who challenges every consensus view",

    # Domain Experts
    "Former Premier League coach with 30 years of tactical data",
    "Cricket statistician who has memorized every Test since 1877",
    "UFC fight analyst trained under Greg Jackson",
    "Wall Street quant with 20 years of trading floor experience",
    "Geopolitical strategist advising NATO think tanks",
    "Medical researcher citing only peer-reviewed trials",
    "Climate scientist with IPCC panel experience",
    "Neuroscientist explaining human behavior through brain chemistry",
    "Historian who has read every primary source document",
    "Anthropologist studying human tribal behavior patterns",

    # Philosophers & Thinkers
    "Stoic philosopher applying Marcus Aurelius to modern problems",
    "Utilitarian who maximizes total happiness in every argument",
    "Kantian ethicist applying categorical imperatives",
    "Nietzschean who questions all conventional morality",
    "Pragmatist philosopher — if it works, it's true",
    "Existentialist focused on individual freedom and responsibility",
    "Postmodern critic deconstructing all grand narratives",
    "Ancient Greek Sophist who can argue any side with equal skill",
    "Rationalist building arguments from first principles only",
    "Dialectical materialist analyzing material conditions",

    # Cultural & Political Voices
    "Progressive activist with social justice framework",
    "Classical liberal defending individual liberty above all",
    "Conservative traditionalist citing historical precedent",
    "Libertarian who thinks most problems are government-caused",
    "Social democrat focused on collective wellbeing",
    "Nationalist citing sovereignty and cultural identity",
    "Globalist arguing interconnected world benefits everyone",
    "Anarchist questioning all authority structures",
    "Technocrat who believes experts should make decisions",
    "Populist channeling the voice of the frustrated majority",

    # Specialists by Region
    "South Asian perspective — India, Pakistan, cricket, geopolitics",
    "East Asian analyst — China, Japan, Korea, economic power",
    "African strategic thinker — colonialism, development, resources",
    "Latin American voice — inequality, revolution, football culture",
    "Middle Eastern analyst — oil, religion, geopolitical chess",
    "European federalist — multilateral institutions, soft power",
    "American exceptionalist — global leadership, market capitalism",
    "Scandinavian social democratic model advocate",
    "Russian geopolitical realist — sphere of influence doctrine",
    "Australian pragmatist — trade, climate, Indo-Pacific strategy",

    # Industry Insiders
    "Silicon Valley venture capitalist betting on disruption",
    "Investment banker modeling every argument like an LBO",
    "Startup founder who thinks speed beats everything",
    "Management consultant who frameworks every problem",
    "Hedge fund manager with contrarian macro thesis",
    "Central banker focused on monetary stability",
    "Supply chain expert who thinks logistics is everything",
    "Energy industry veteran who has worked oil, gas, and renewables",
    "Pharmaceutical executive who understands drug economics",
    "Real estate mogul who sees every trend through property lens",

    # Scientists & Technologists
    "Physicist applying thermodynamics and entropy to social systems",
    "Evolutionary biologist explaining everything through natural selection",
    "Cognitive scientist studying how minds form beliefs",
    "Computer scientist modeling problems algorithmically",
    "Mathematician who only accepts proven axioms",
    "Chemist who reduces everything to molecular interactions",
    "Geneticist who sees inherited traits behind every behavior",
    "Astronomer with cosmic-scale perspective on human concerns",
    "Environmental scientist measuring planetary boundaries",
    "Robotics engineer predicting automation's social impact",

    # Unconventional Thinkers
    "Devil's advocate who argues the least popular position",
    "Futurist projecting 50 years forward on every topic",
    "Historian of science cataloging paradigm shifts",
    "Propaganda analyst detecting manipulation in all arguments",
    "Black swan hunter looking for tail-risk scenarios",
    "Steelman master who makes even weak arguments iron-strong",
    "Pattern recognition genius who finds hidden correlations",
    "Cross-disciplinary synthesizer connecting unrelated fields",
    "Myth-buster armed with fact-checking databases",
    "Epistemologist questioning what we can actually know",

    # Practitioners & Operators
    "Special forces operator with direct operational experience",
    "Emergency room doctor who has seen what actually kills people",
    "Field journalist who has reported from 40 conflict zones",
    "Teacher who has spent 25 years watching how humans learn",
    "Judge who has applied legal reasoning for 30 years",
    "Diplomat trained in negotiation and conflict resolution",
    "Intelligence analyst who thinks in probabilities and sources",
    "Public health official who has managed three epidemics",
    "Urban planner who has designed cities for 2 million people",
    "Agricultural scientist who has fed communities in crisis",

    # Wildcards
    "12-year-old who asks brutally obvious questions adults ignore",
    "100-year-old who has seen five versions of every crisis",
    "Anthropologist from 200 years in the future studying us",
    "Detective applying Sherlock Holmes logic to evidence",
    "Poet who cuts through noise to emotional truth",
    "Stand-up comedian who uses ridicule to expose absurdity",
    "Monk with 40 years of silent contemplation on human nature",
    "Former cult member who knows how groupthink destroys truth",
    "Whistleblower who has exposed three major institutions",
    "Synthesizer who finds the ONE thing everyone is missing"
]


class DebateEngine:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    async def run_debate(self, question: str) -> str:
        """Run the full 3-round debate and return formatted result."""
        
        # Round 1: All 100 personas give positions
        round1_result = await self._round1(question)
        
        # Round 2: Top 5 clash
        round2_result = await self._round2(question, round1_result)
        
        # Format final output
        return self._format_output(question, round2_result)

    async def _round1(self, question: str) -> str:
        """Get all 100 positions in one Gemini call."""
        
        personas_text = "\n".join([f"{i+1}. {p}" for i, p in enumerate(PERSONAS)])
        
        prompt = f"""You are running a structured intellectual debate with 100 distinct expert personas.

QUESTION: {question}

Here are all 100 personas:
{personas_text}

Your task:
1. For each of the 100 personas above, write their position on the question in 1-2 sentences
2. Each position MUST include a specific data point, statistic, historical fact, or logical principle
3. Mark the 5 STRONGEST positions with ⭐ at the start
4. The 5 strongest should be the ones with the most compelling data-backed arguments

Format each entry as:
[Number]. [Persona name]: [Their position with data]

After all 100 positions, write:
---TOP 5 SELECTED---
List the numbers of the 5 strongest positions.

Be direct. No preamble. Start with position 1 immediately."""

        response = await asyncio.to_thread(
            self.model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=8000,
                temperature=0.9,
            )
        )
        return response.text

    async def _round2(self, question: str, round1: str) -> str:
        """Top 5 clash and produce final verdict."""
        
        prompt = f"""You are the Arena judge overseeing a championship debate round.

ORIGINAL QUESTION: {question}

ROUND 1 RESULTS (100 positions with top 5 marked):
{round1[:6000]}

Now run ROUND 2 — the championship clash:

Extract the 5 strongest positions from Round 1.
Have them directly attack each other's weakest points.
Each champion gets 2-3 sentences to counter the others.

Then declare a FINAL VERDICT:
- Which argument won and WHY
- What data/logic made it unbeatable
- What the runner-up got right
- The one insight that everyone missed

Format your response as:

⚔️ ROUND 2 — CHAMPIONSHIP CLASH

[Champion 1 name]: [Their attack on the field]
[Champion 2 name]: [Their counter-argument]
[Champion 3 name]: [Their angle]
[Champion 4 name]: [Their position]
[Champion 5 name]: [Their stance]

🏆 FINAL VERDICT

**Winner:** [Name]
**Winning argument:** [2-3 sentences on why this argument is unbeatable]
**Key data that decided it:** [The specific fact/stat/logic]
**Runner-up:** [Name] — [What they got right]
**The insight everyone missed:** [1 sentence that reframes the whole debate]

Be decisive. The arena demands a clear winner."""

        response = await asyncio.to_thread(
            self.model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=2000,
                temperature=0.8,
            )
        )
        return response.text

    def _format_output(self, question: str, round2: str) -> str:
        """Format the final output for Telegram."""
        
        output = f"""🏟️ *THE ARENA HAS SPOKEN*

*Question:* _{question}_

{round2}

---
_100 minds debated. 5 champions clashed. One truth remains._
_Ask another question to re-enter the arena._"""

        # Clean up any markdown that breaks Telegram
        output = output.replace("**", "*")
        
        return output
