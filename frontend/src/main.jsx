import { useEffect, useState } from "react";

import { createRoot } from "react-dom/client";

import "./style.css";



const API =

  import.meta.env.VITE_API_URL ||

  "http://127.0.0.1:8000";



function formatTime(seconds) {

  const mins = Math.floor(seconds / 60);

  const secs = seconds % 60;



  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(

    2,

    "0"

  )}`;

}



function App() {

  const [screen, setScreen] = useState("home");



  const [duration, setDuration] = useState(10);

  const [environment, setEnvironment] = useState("anywhere");

  const [difficulty, setDifficulty] = useState("medium");



  const [caseData, setCaseData] = useState(null);

  // Persistent player stats come from the backend.
  const [player, setPlayer] = useState({
    total_xp: 0,
    cases_solved: 0,
    cases_attempted: 0,
    level: 1,
    level_name: "INITIATE",
    level_xp: 0,
    next_level_xp: 250,
    xp_to_next_level: 250,
    level_progress: 0,
  });
  const [playerLoading, setPlayerLoading] = useState(true);



  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");



  const [timeLeft, setTimeLeft] = useState(0);

  const [timerEnd, setTimerEnd] = useState(null);



  const [file, setFile] = useState(null);

  const [result, setResult] = useState(null);



  // Hints revealed during the current case

  const [revealedClues, setRevealedClues] = useState([]);



  // Total reduction from the potential reward

  const [hintCost, setHintCost] = useState(0);
  const [hintLoading, setHintLoading] = useState(false);



  // --------------------------------------------------
  // PLAYER STATS
  // --------------------------------------------------

  async function loadPlayerStats() {
    try {
      const response = await fetch(`${API}/api/player`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to load player stats.");
      }

      setPlayer(data);
    } catch (err) {
      console.error("Player stats error:", err);
    } finally {
      setPlayerLoading(false);
    }
  }

  useEffect(() => {
    loadPlayerStats();
  }, []);

  // --------------------------------------------------

  // TIMER

  // --------------------------------------------------



  useEffect(() => {

    if (!timerEnd) return;



    const interval = setInterval(() => {

      const remaining = Math.max(

        0,

        Math.ceil((timerEnd - Date.now()) / 1000)

      );



      setTimeLeft(remaining);



      if (remaining <= 0) {

        clearInterval(interval);

        setTimerEnd(null);



        if (screen === "case") {

          setScreen("timeout");

        }

      }

    }, 250);



    return () => clearInterval(interval);

  }, [timerEnd, screen]);



  // --------------------------------------------------

  // GENERATE CASE

  // --------------------------------------------------



  async function generateCase() {

    setLoading(true);

    setError("");



    try {

      const response = await fetch(`${API}/api/cases`, {

        method: "POST",

        headers: {

          "Content-Type": "application/json",

        },

        body: JSON.stringify({

          environment,

          duration,

          difficulty,

        }),

      });



      const data = await response.json();



      if (!response.ok) {

        throw new Error(

          data.detail || "Failed to generate case."

        );

      }



      setCaseData(data);



      // Reset case state

      setRevealedClues([]);

      setHintCost(0);

      setResult(null);

      setFile(null);



      const end = Date.now() + duration * 60 * 1000;



      setTimerEnd(end);

      setTimeLeft(duration * 60);



      setScreen("case");

    } catch (err) {

      console.error(err);

      setError(

        err.message || "Something went wrong."

      );

    } finally {

      setLoading(false);

    }

  }



  // --------------------------------------------------

  // HINTS

  // --------------------------------------------------



  function getClueCost(index) {

    return 25 * (index + 1);

  }



  async function revealClue(index) {
    if (!caseData?.clues) return;

    if (revealedClues.includes(index) || hintLoading) {
      return;
    }

    setHintLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("clue_index", String(index));

      const response = await fetch(
        `${API}/api/cases/${caseData.case_id}/hint`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to reveal hint."
        );
      }

      setRevealedClues((prev) => {
        if (prev.includes(index)) return prev;
        return [...prev, index];
      });

      // The backend is authoritative for hint costs.
      setHintCost(data.hint_cost || 0);
    } catch (err) {
      console.error(err);
      setError(
        err.message || "Failed to reveal hint."
      );
    } finally {
      setHintLoading(false);
    }
  }


  function getPotentialXP() {

    return caseData?.xp || 0;

  }



  function getFinalXP() {

    return Math.max(

      0,

      getPotentialXP() - hintCost

    );

  }



  // --------------------------------------------------

  // SUBMIT EVIDENCE

  // --------------------------------------------------



  async function submitEvidence() {

    if (!file || !caseData) return;



    setLoading(true);

    setError("");



    try {

      const formData = new FormData();



      formData.append(

        "image",

        file

      );



      const response = await fetch(

        `${API}/api/cases/${caseData.case_id}/evidence`,

        {

          method: "POST",

          body: formData,

        }

      );



      const data = await response.json();



      if (!response.ok) {

        throw new Error(

          data.detail ||

            "Evidence verification failed."

        );

      }



      setResult(data);




      // Backend is authoritative for persistent XP.



      if (data.passed) {



        await loadPlayerStats();



      }




      if (data.passed) {

        setScreen("solved");

      } else {

        setScreen("feedback");

      }

    } catch (err) {

      console.error(err);



      setError(

        err.message ||

          "Evidence submission failed."

      );

    } finally {

      setLoading(false);

    }

  }



  // --------------------------------------------------

  // RETRY SAME CASE

  // --------------------------------------------------



  function retryCase() {

    setFile(null);

    setResult(null);



    const end = Date.now() + duration * 60 * 1000;



    setTimerEnd(end);

    setTimeLeft(duration * 60);



    setScreen("case");

  }



  // --------------------------------------------------

  // NEW CASE

  // --------------------------------------------------



  function newCase() {

    setFile(null);

    setResult(null);

    setCaseData(null);



    setRevealedClues([]);

    setHintCost(0);



    setTimerEnd(null);

    setTimeLeft(0);



    setScreen("setup");

  }



  // ==================================================

  // HOME

  // ==================================================



  if (screen === "home") {

    return (

      <main className="app">

        <div className="scanline" />



        <section className="center">

          <p className="eyebrow">

            REALITY.EXE // FIELD PROTOCOL

          </p>



          <h1>

            TOUCH

            <br />

            <span>GRASS.</span>

          </h1>



          <p className="sub">

            Some problems can't be solved on a screen.

          </p>




          <div className="progressCard">
            <div className="progressTop">
              <span>
                LEVEL {playerLoading ? "—" : player.level}
              </span>
              <strong>
                {playerLoading ? "—" : player.level_name}
              </strong>
            </div>

            <div className="progressTrack">
              <div
                className="progressFill"
                style={{
                  width: `${playerLoading ? 0 : player.level_progress}%`,
                }}
              />
            </div>

            <div className="progressBottom">
              <span>
                {playerLoading ? "—" : player.total_xp} XP
              </span>
              <span>
                {playerLoading
                  ? "—"
                  : player.xp_to_next_level > 0
                    ? `${player.xp_to_next_level} XP TO NEXT`
                    : "MAX LEVEL"}
              </span>
            </div>
          </div>

          <div className="playerBar">
            <span>
              CASES <strong>{playerLoading ? "—" : player.cases_solved}</strong>
            </span>
          </div>





          <button

            className="primary"

            onClick={() =>

              setScreen("setup")

            }

          >

            START MISSION

            <b>→</b>

          </button>

        </section>

      </main>

    );

  }



  // ==================================================

  // SETUP

  // ==================================================



  if (screen === "setup") {

    return (

      <main className="app">

        <div className="scanline" />



        <section className="panel">

          <p className="eyebrow">

            REALITY.EXE // CONFIGURATION

          </p>



          <h2>Prepare.</h2>




          <div className="progressCard">
            <div className="progressTop">
              <span>
                LEVEL {playerLoading ? "—" : player.level}
              </span>
              <strong>
                {playerLoading ? "—" : player.level_name}
              </strong>
            </div>

            <div className="progressTrack">
              <div
                className="progressFill"
                style={{
                  width: `${playerLoading ? 0 : player.level_progress}%`,
                }}
              />
            </div>

            <div className="progressBottom">
              <span>
                {playerLoading ? "—" : player.total_xp} XP
              </span>
              <span>
                {playerLoading
                  ? "—"
                  : player.xp_to_next_level > 0
                    ? `${player.xp_to_next_level} XP TO NEXT`
                    : "MAX LEVEL"}
              </span>
            </div>
          </div>

          <div className="playerBar">
            <span>
              SOLVED <strong>{playerLoading ? "—" : player.cases_solved}</strong>
            </span>
          </div>





          <div className="label">

            TIME LIMIT

          </div>



          <div className="choices">

            {[5, 10, 20, 30].map(

              (value) => (

                <button

                  key={value}

                  className={`choice ${

                    duration === value

                      ? "active"

                      : ""

                  }`}

                  onClick={() =>

                    setDuration(value)

                  }

                >

                  {value} MIN

                </button>

              )

            )}

          </div>



          <div className="label">

            ENVIRONMENT

          </div>



          <div className="choices">

            {[

              "anywhere",

              "campus",

              "park",

            ].map((value) => (

              <button

                key={value}

                className={`choice ${

                  environment === value

                    ? "active"

                    : ""

                }`}

                onClick={() =>

                  setEnvironment(value)

                }

              >

                {value.toUpperCase()}

              </button>

            ))}

          </div>



          <div className="label">

            DIFFICULTY

          </div>



          <div className="choices">

            {[

              "easy",

              "medium",

              "hard",

            ].map((value) => (

              <button

                key={value}

                className={`choice ${

                  difficulty === value

                    ? "active"

                    : ""

                }`}

                onClick={() =>

                  setDifficulty(value)

                }

              >

                {value.toUpperCase()}

              </button>

            ))}

          </div>



          {error && (

            <p className="error">

              {error}

            </p>

          )}



          <button

            className="primary"

            disabled={loading}

            onClick={generateCase}

          >

            {loading

              ? "GENERATING..."

              : "GENERATE CASE"}



            {!loading && <b>→</b>}

          </button>

        </section>

      </main>

    );

  }



  // ==================================================

  // CASE

  // ==================================================



  if (

    screen === "case" &&

    caseData

  ) {

    return (

      <main className="app">

        <div className="scanline" />



        <section className="case">

          <div className="caseTop">

            <span>

              CASE // {caseData.case_id}

            </span>




            <span className="caseStats">




              XP {playerLoading ? "—" : player.total_xp}




            </span>





            <span

              className={`timer ${

                timeLeft <= 30

                  ? "danger"

                  : ""

              }`}

            >

              {formatTime(timeLeft)}

            </span>

          </div>



          <p className="eyebrow">

            FIELD OBJECTIVE

          </p>



          <h2>

            {caseData.title}

          </h2>



          <p className="objective">

            {caseData.objective}

          </p>



          <div className="warning">

            <span>⚠</span>{" "}

            PUT THE PHONE AWAY.

            <br />

            RETURN ONLY WHEN YOU HAVE

            <br />

            SOMETHING TO SHOW.

          </div>



          {/* MISSION REWARD */}



          <div className="clue">

            <small>

              MISSION REWARD

            </small>



            <strong>

              {getPotentialXP()} XP

            </strong>



            {hintCost > 0 && (

              <p

                style={{

                  margin: "8px 0 0",

                  color: "#7c9180",

                  fontSize: "14px",

                }}

              >

                Current reward:{" "}

                <strong>

                  {getFinalXP()} XP

                </strong>

              </p>

            )}

          </div>



          {/* PRIMARY ACTION */}



          <button

            className="primary"

            onClick={() =>

              setScreen("evidence")

            }

          >

            I FOUND SOMETHING

            <b>→</b>

          </button>



          {/* HINTS */}



          <div className="label">

            HINTS

          </div>



          {caseData.clues?.map(

            (clue, index) => {

              const revealed =

                revealedClues.includes(

                  index

                );



              const cost =

                getClueCost(index);



              return (

                <div

                  className="clue"

                  key={index}

                >

                  <small>

                    HINT {index + 1}

                  </small>



                  {revealed ? (

                    <strong>

                      {clue}

                    </strong>

                  ) : (

                    <>

                      <strong

                        style={{

                          opacity: 0.35,

                          letterSpacing:

                            "0.08em",

                        }}

                      >

                        █████████████

                      </strong>



                      <button
                        className="secondary"
                        disabled={hintLoading}
                        onClick={() =>
                          revealClue(index)
                        }
                      >
                        {hintLoading
                          ? "REVEALING..."
                          : `REVEAL HINT — ${cost} XP`}
                      </button>

                    </>

                  )}

                </div>

              );

            }

          )}



          {error && (

            <p className="error">

              {error}

            </p>

          )}



          {/* SECONDARY ACTION */}



          <button

            className="secondary dangerButton"

            onClick={newCase}

          >

            NEW CASE

          </button>

        </section>

      </main>

    );

  }



  // ==================================================

  // EVIDENCE

  // ==================================================



  if (screen === "evidence") {

    return (

      <main className="app">

        <div className="scanline" />



        <section className="panel">

          <p className="eyebrow">

            EVIDENCE // SUBMISSION

          </p>



          <h2>Show me.</h2>



          <p className="sub">

            Photograph what you found.

            The AI will determine whether

            it satisfies the case.

          </p>



          <label className="drop">

            <input

              type="file"

              accept="image/*"

              capture="environment"

              onChange={(e) =>

                setFile(

                  e.target.files?.[0] ||

                    null

                )

              }

            />



            {file

              ? file.name

              : "TAP TO TAKE A PHOTO"}

          </label>



          {error && (

            <p className="error">

              {error}

            </p>

          )}



          <button

            className="primary"

            disabled={!file || loading}

            onClick={submitEvidence}

          >

            {loading

              ? "AI IS EXAMINING..."

              : "SUBMIT EVIDENCE"}



            {!loading && <b>→</b>}

          </button>



          <button

            className="secondary"

            onClick={() =>

              setScreen("case")

            }

          >

            BACK TO CASE

          </button>

        </section>

      </main>

    );

  }



  // ==================================================

  // FAILED EVIDENCE

  // ==================================================



  if (screen === "feedback") {

    const observation =

      result?.observation ||

      "The AI could not determine what was visible in the photograph.";



    const reason =

      result?.reason ||

      result?.message ||

      "The evidence does not satisfy the case.";



    return (

      <main className="app">

        <div className="scanline" />



        <section className="case">

          <p className="eyebrow">

            AI VERIFICATION

          </p>



          <h2>

            Not quite.

          </h2>



          {/* WHAT AI FOUND */}



          <div className="clue">

            <small>

              AI FOUND

            </small>



            <strong>

              {observation}

            </strong>

          </div>



          {/* WHY IT FAILED */}



          <div className="clue">

            <small>

              WHY IT FAILED

            </small>



            <strong>

              {reason}

            </strong>

          </div>



          <div className="warning">

            <span>×</span>{" "}

            THE EVIDENCE DOES NOT

            <br />

            SATISFY THE CASE.

          </div>



          <button

            className="primary"

            onClick={() => {

              setFile(null);

              setScreen("evidence");

            }}

          >

            TRY ANOTHER PHOTO

            <b>→</b>

          </button>



          <button

            className="secondary"

            onClick={() =>

              setScreen("case")

            }

          >

            KEEP SEARCHING

          </button>



          <button

            className="secondary dangerButton"

            onClick={newCase}

          >

            NEW CASE

          </button>

        </section>

      </main>

    );

  }



  // ==================================================

  // SOLVED

  // ==================================================



  if (screen === "solved") {

    const observation =

      result?.observation ||

      "The AI verified your evidence.";



    const finalXP =

      getFinalXP();



    return (

      <main className="app">

        <div className="scanline" />



        <section className="case solved">

          <div className="stamp">

            VERIFIED

          </div>



          <p className="eyebrow">

            CASE COMPLETE

          </p>



          <h2>

            You found

            <br />

            it.

          </h2>



          {/* WHAT AI FOUND */}



          <div className="clue">

            <small>

              AI FOUND

            </small>



            <strong>

              {observation}

            </strong>

          </div>



          {/* REWARD */}



          <div className="clue">

            <small>

              REWARD

            </small>



            <strong>

              +{result?.xp_earned ?? finalXP} XP

            </strong>



            {hintCost > 0 && (

              <p

                style={{

                  margin: "8px 0 0",

                  color: "#7c9180",

                }}

              >

                {result?.hint_cost ?? hintCost} XP deducted

                from the potential

                reward for hints.

              </p>

            )}

          </div>




          {result?.level_up && (
            <div className="levelUp">
              <small>LEVEL UP</small>
              <strong>
                LEVEL {result.previous_level} → LEVEL {result.level}
              </strong>
              <span>{result.level_name}</span>
            </div>
          )}

          <div className="progressCard">
            <div className="progressTop">
              <span>LEVEL {player.level}</span>
              <strong>{player.level_name}</strong>
            </div>

            <div className="progressTrack">
              <div
                className="progressFill"
                style={{ width: `${player.level_progress}%` }}
              />
            </div>

            <div className="progressBottom">
              <span>{player.total_xp} XP</span>
              <span>
                {player.xp_to_next_level > 0
                  ? `${player.xp_to_next_level} XP TO NEXT`
                  : "MAX LEVEL"}
              </span>
            </div>
          </div>

          <div className="playerBar">
            <span>
              CASES SOLVED <strong>{player.cases_solved}</strong>
            </span>
          </div>





          <div className="warning">

            <span>✓</span>{" "}

            THE REAL WORLD

            <br />

            PROVIDED THE ANSWER.

          </div>



          <button

            className="primary"

            onClick={newCase}

          >

            NEW CASE

            <b>→</b>

          </button>

        </section>

      </main>

    );

  }



  // ==================================================

  // TIMEOUT

  // ==================================================



  if (screen === "timeout") {

    return (

      <main className="app">

        <div className="scanline" />



        <section className="case">

          <p className="eyebrow">

            FIELD PROTOCOL // TIME

          </p>



          <h2>

            Time's

            <br />

            up.

          </h2>



          <p className="objective">

            The mission window has closed.

          </p>



          <div className="warning">

            <span>00:00</span>

            <br />

            MISSION EXPIRED.

          </div>



          <button

            className="primary"

            onClick={retryCase}

          >

            TRY AGAIN

            <b>→</b>

          </button>



          <button

            className="secondary"

            onClick={newCase}

          >

            NEW CASE

          </button>

        </section>

      </main>

    );

  }



  return null;

}



createRoot(

  document.getElementById("root")

).render(

  <App />

);