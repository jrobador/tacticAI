import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * The clock of the match page: the <video> (muted, looping, no native controls) or, without a file, a stand-in clock.
 * `time` is the video time in seconds, refreshed every 100 ms while it plays and at once on a seek.
 */
export function usePlayback(src: string | null, duration: number, rate = 1) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [failed, setFailed] = useState(false)
  const standIn = src === null || failed
  const clock = useRef(0)

  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => {
      if (standIn) {
        clock.current = clock.current + 0.1 >= duration ? 0 : clock.current + 0.1
        setTime(clock.current)
      } else if (videoRef.current) {
        // Set on every tick: the <video> can remount or reload its source, and either resets the rate.
        if (videoRef.current.playbackRate !== rate) videoRef.current.playbackRate = rate
        setTime(videoRef.current.currentTime)
      }
    }, 100)
    return () => clearInterval(id)
  }, [playing, standIn, duration, rate])

  const seek = useCallback((t: number) => {
    const v = videoRef.current
    if (v && !standIn) v.currentTime = t
    clock.current = t
    setTime(t)
  }, [standIn])

  const play = useCallback((on: boolean) => {
    setPlaying(on)
    const v = videoRef.current
    if (!v || standIn) return
    if (on) v.play().catch(() => setPlaying(false))
    else v.pause()
  }, [standIn])

  return {
    videoRef, time, playing, standIn, seek, play,
    toggle: () => play(!playing),
    onPlay: () => setPlaying(true),
    onPause: () => setPlaying(false),
    onTimeUpdate: (t: number) => setTime(t),
    onError: () => setFailed(true),
  }
}
