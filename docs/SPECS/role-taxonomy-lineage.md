# Lineage: the 5-role taxonomy (removed from Tierllama 2026-09-23)

DIRECTOR / SCREENWRITER / TEACHER / BUG_REPORTER / NAVIGATOR were designed in
**comfyui-video-ui** (role-router brainstorm, committed 2026-09-07) as the
persona taxonomy for an AI video workspace: which AGENT should handle a
message. Tierllama J1 (2026-09-21) implemented the classifier using the same
5 roles - a design reuse, not memory contamination, but a scope error: a
generic router does not need persona labels, and the vocabulary caused
cross-project confusion (Gui, 2026-09-23).

**Removed from Tierllama:** classifier.py (ROLES, classify_role, rubric
Roles block), router.py (log fields), jev_cloud.py (systemone question),
golden set truth.role. Lane selection never depended on role (difficulty x
timing only) - removal is functionally safe, verified E2E.

The roles remain canonical in **comfyui-video-ui** (Director = multi-role
agent persona, emotion engine, etc). If Tierllama later needs
message-type metadata again, design a router-native taxonomy there - do not
import project personas.
