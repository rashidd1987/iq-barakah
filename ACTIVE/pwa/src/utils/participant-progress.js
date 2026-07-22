const VALID_LEVELS = new Set(['А', 'Б', 'В', 'Г'])
const VALID_SKILLS = new Set(['I', 'II', 'III'])

export function applyParticipantProgress(participant, state, save) {
  if (!participant || !VALID_LEVELS.has(participant.level)) return false
  const globalWeek = Number(participant.global_week)
  if (!Number.isInteger(globalWeek) || globalWeek < 1 || globalWeek > 30) return false

  state.level = participant.level
  state.currentWeek = globalWeek
  state.skill = VALID_SKILLS.has(participant.vakt_level) ? participant.vakt_level : 'I'
  save('level', state.level)
  save('currentWeek', state.currentWeek)
  save('skill', state.skill)
  return true
}
