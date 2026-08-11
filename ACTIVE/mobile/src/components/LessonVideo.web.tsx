import React, { useMemo } from 'react'
import { Text, View } from 'react-native'
import { useTheme } from '../context/ThemeContext'
import { radius, ThemeColors } from '../theme/colors'

type Props = { title?: string; url: string }

export default function LessonVideo({ title, url }: Props) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])

  return (
    <View style={styles.card}>
      <Text style={styles.eyebrow}>ВИДЕО К УРОКУ</Text>
      {!!title && <Text style={styles.title}>{title}</Text>}
      {React.createElement('video', {
        'aria-label': title || 'Видео к уроку',
        controls: true,
        controlsList: 'nodownload noremoteplayback',
        disablePictureInPicture: true,
        onContextMenu: (event: Event) => event.preventDefault(),
        playsInline: true,
        preload: 'metadata',
        src: url,
        style: styles.video,
      })}
      <Text style={styles.hint}>Видео доступно только внутри авторизованного урока.</Text>
    </View>
  )
}

const createStyles = (colors: ThemeColors) => ({
  card: {
    marginTop: 14, padding: 16, borderRadius: radius.card,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  eyebrow: { color: colors.gold, fontSize: 10, fontWeight: '900' as const, letterSpacing: 0.9 },
  title: { color: colors.text, fontSize: 17, fontWeight: '800' as const, lineHeight: 23, marginTop: 8 },
  video: { width: '100%', aspectRatio: '16 / 9', borderRadius: 12, marginTop: 12, backgroundColor: '#000' },
  hint: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 10 },
})
