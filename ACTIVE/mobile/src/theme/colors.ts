export type ThemePalette = 'classic' | 'feminine'
export type ThemeMode = 'system' | 'light' | 'dark'
export type ResolvedThemeMode = 'light' | 'dark'

export interface ThemeColors {
  g1: string
  g2: string
  g3: string
  gpale: string
  gsoft: string
  gold: string
  gold2: string
  goldpale: string
  bg: string
  card: string
  cardRaised: string
  text: string
  sub: string
  muted: string
  border: string
  completed: string
  incomplete: string
  successSoft: string
  danger: string
  dangerSoft: string
  onPrimary: string
  overlay: string
  shadow: string
}

const classicLight: ThemeColors = {
  g1: '#173D2A',
  g2: '#2E6847',
  g3: '#3D7A54',
  gpale: '#E8F1E9',
  gsoft: '#D8E5DA',
  gold: '#C9A84C',
  gold2: '#E0C572',
  goldpale: '#FBF4DF',
  bg: '#F7F5EE',
  card: '#FCFBF7',
  cardRaised: '#FFFFFF',
  text: '#18221B',
  sub: '#59635B',
  muted: '#899189',
  border: '#DDE3DB',
  completed: '#74866A',
  incomplete: '#8B928A',
  successSoft: '#E8F1E9',
  danger: '#A64B43',
  dangerSoft: '#F8E9E6',
  onPrimary: '#F8F4E8',
  overlay: 'rgba(23,61,42,0.08)',
  shadow: '#102218',
}

const classicDark: ThemeColors = {
  g1: '#0D1A12',
  g2: '#1A3D08',
  g3: '#2A5C10',
  gpale: '#17251B',
  gsoft: '#223327',
  gold: '#C9A84C',
  gold2: '#E8C97A',
  goldpale: '#F5DFA0',
  bg: '#070B04',
  card: '#0E160F',
  cardRaised: '#121D14',
  text: '#F8F4E8',
  sub: '#B8B8AE',
  muted: '#858A80',
  border: 'rgba(201,168,76,0.18)',
  completed: '#71825F',
  incomplete: '#777C70',
  successSoft: '#1D2A1F',
  danger: '#D88478',
  dangerSoft: '#2D1A18',
  onPrimary: '#F8F4E8',
  overlay: 'rgba(201,168,76,0.08)',
  shadow: '#000000',
}

const feminineLight: ThemeColors = {
  g1: '#3D2835',
  g2: '#7B5365',
  g3: '#9A6878',
  gpale: '#F5E9EB',
  gsoft: '#ECDADC',
  gold: '#C6A15B',
  gold2: '#D9BC7C',
  goldpale: '#FBF1DD',
  bg: '#FAF6F0',
  card: '#FFFDFC',
  cardRaised: '#FFFFFF',
  text: '#3D2835',
  sub: '#74636A',
  muted: '#9B8C91',
  border: '#EBDADD',
  completed: '#74866A',
  incomplete: '#A77482',
  successSoft: '#ECF2E9',
  danger: '#A64B5B',
  dangerSoft: '#F8E8EC',
  onPrimary: '#FFF9F5',
  overlay: 'rgba(185,122,133,0.09)',
  shadow: '#3D2835',
}

const feminineDark: ThemeColors = {
  g1: '#241720',
  g2: '#593A49',
  g3: '#744C5D',
  gpale: '#2B2029',
  gsoft: '#392A35',
  gold: '#C6A15B',
  gold2: '#D8B873',
  goldpale: '#F1DDB5',
  bg: '#160F17',
  card: '#1D151D',
  cardRaised: '#241A23',
  text: '#F7EFE7',
  sub: '#C1AFB5',
  muted: '#927F86',
  border: 'rgba(198,161,91,0.17)',
  completed: '#71815F',
  incomplete: '#A96E80',
  successSoft: '#252C21',
  danger: '#D98798',
  dangerSoft: '#321C25',
  onPrimary: '#FFF8F3',
  overlay: 'rgba(185,122,133,0.10)',
  shadow: '#000000',
}

export const themes: Record<ThemePalette, Record<ResolvedThemeMode, ThemeColors>> = {
  classic: { light: classicLight, dark: classicDark },
  feminine: { light: feminineLight, dark: feminineDark },
}

export const radius = {
  card: 18,
  button: 14,
}

export const makeShadow = (colors: ThemeColors) => ({
  card: {
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: colors.bg === '#070B04' || colors.bg === '#160F17' ? 0.24 : 0.08,
    shadowRadius: 14,
    elevation: 3,
  },
})
