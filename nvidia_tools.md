HikeGuard NVIDIA Tool Recommendation

Use **NVIDIA NeMo Agent Toolkit** as the main framework, with **Nemotron 3.5 Lightning** as the language model if the hackathon organizers provide it.

## 1. Clarifying AIQ

NVIDIA's **Agent Intelligence Toolkit**, previously called **AIQ**, was renamed **NeMo Agent Toolkit**. This likely explains the reference to AIQ in the Hiking Safety Assistant challenge brief; confirm the intended starter project with a mentor.

The separate **AI-Q research blueprint** is a different project.

Source: [NVIDIA NeMo Agent Toolkit](https://developer.nvidia.com/agent-intelligence-toolkit?ncid=no-ncid).

## 2. Recommended Components

| Component | Role in HikeGuard |
| --- | --- |
| **NeMo Agent Toolkit — formerly AIQ** | Coordinate route retrieval, weather retrieval, risk calculation and explanations. |
| **Nemotron 3.5 Lightning** | Understand user questions, call tools and explain the assessment. Use it if available in the organizers' environment. |
| **NVIDIA NIM, if supplied** | Access the model through the organizers' deployed API. Confirm the endpoint, model identifier and authentication method. |
| **HPE compute instance** | Run the backend and, depending on the provided setup, the model. |

NeMo Agent Toolkit supports connecting to tools through MCP. Your team can expose route and weather functions through MCP as the implementation develops.

Sources: [NeMo Agent Toolkit documentation](https://docs.nvidia.com/nemo/agent-toolkit/latest/), [NVIDIA Nemotron model catalog](https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/llm-info/).

## 3. Evidence from the Preparation Webinar

The following points come from the supplied webinar transcript:

| Timestamp | What the speaker describes | Implication for HikeGuard |
| --- | --- | --- |
| **8:38–9:18** | Accelerated compute resources and facilitator support for deploying models, blueprints and agentic tools. | Start with the provided environment and ask mentors for the supported deployment path. |
| **2:02:33–2:02:56** | The speaker highlights 3.5 Lightning for agentic workflows and tool calling. | It is a suitable first model to request for this tool-driven assistant. |
| **1:31–1:50** | Secure-agent tools are presented as an available hackathon direction. | The excerpt does not establish them as mandatory for every challenge. |

The uploaded transcript jumps from **9:34 to 2:02:33**. Most technical demonstrations and installation instructions are therefore absent. It does not confirm an exact model endpoint, preinstalled stack or starter repository.

## 4. Proposed HikeGuard Workflow

```text
Hiker's question
      |
      v
NeMo Agent Toolkit
      |-- Retrieve route and terrain
      |-- Retrieve weather
      |-- Run the team's Python safety rules
      |
      v
Nemotron explains the assessment
      |
      v
Map + segment risks + alternative plan
```

The **safety rules engine is built by the HikeGuard team**. NVIDIA provides orchestration and the language model; your code determines which risk rules apply.

The model explains the assessment, supporting evidence and uncertainty. Changes to departure time, route or user profile must trigger a fresh assessment before the model explains the revised plan.

## 5. Question for the Mentors

> We're building HikeGuard using NeMo Agent Toolkit, formerly AIQ. Can you give us the starter repository and a Nemotron endpoint—preferably 3.5 Lightning—on the provided HPE environment?

Confirm the supported software version, model identifier, API URL, authentication method and backend deployment location before installation.
