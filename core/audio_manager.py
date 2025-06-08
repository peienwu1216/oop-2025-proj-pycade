# core/audio_manager.py

import pygame
import settings

class AudioManager:
    def __init__(self):
        """
        Initializes the audio manager.
        It maps sound names to their paths for on-demand loading.
        """
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.sound_paths = {
            'hover': settings.MENU_HOVER_SOUND_PATH,
            'tick': settings.BOMB_TICK_PATH,
            'explosion': settings.EXPLOSION_PATH,
            'bling': settings.BLING_PATH,
            'hurt': settings.HURT_PATH,
            'place_bomb': settings.PLACE_BOMB_SOUND_PATH,
        }
        # Sounds are now loaded on demand, so we store running sounds to manage them.
        self.playing_sounds = {}
        self.music_volume = settings.MENU_MUSIC_VOLUME
        self.sfx_volume = 0.5

        pygame.mixer.music.set_volume(self.music_volume)

    def stop_all(self):
        """Stops all music and sound effects."""
        pygame.mixer.music.stop()
        pygame.mixer.stop()
        self.playing_sounds.clear()

    def stop_all_sounds(self):
        """Stops all currently playing sound effects."""
        pygame.mixer.stop() # More direct way to stop all sounds
        self.playing_sounds.clear()

    def play_sound(self, name, loops=0, volume_multiplier=1.0):
        """
        Loads and plays a sound effect on demand.

        Args:
            name (str): The key name of the sound to play.
            loops (int): The number of times to repeat the sound. 0 means play once, -1 means loop forever.
            volume_multiplier (float): A multiplier for the sound's volume (0.0 to 1.0).
        """
        if name in self.sound_paths:
            path = self.sound_paths[name]
            try:
                # Stop the specific sound if it's looping, before playing a new one.
                if name in self.playing_sounds:
                    self.playing_sounds[name].stop()
                    
                sound = pygame.mixer.Sound(path)
                sound.set_volume(self.sfx_volume * volume_multiplier)
                sound.play(loops=loops)
                # If it's a looping sound, keep track of it
                if loops == -1:
                    self.playing_sounds[name] = sound
            except pygame.error as e:
                print(f"Error loading and playing sound '{name}' from '{path}': {e}")
        else:
            print(f"Warning: Sound '{name}' not found in AudioManager.")

    def stop_sound(self, name):
        """
        Stops a specific sound effect from playing.
        This is particularly important for looping sounds.

        Args:
            name (str): The key name of the sound to stop.
        """
        if name in self.playing_sounds:
            self.playing_sounds[name].stop()
            del self.playing_sounds[name]
        # Fallback for non-looping sounds is harder, this prioritizes stoppable sounds.

    def play_music(self, music_path, loops=-1):
        """
        Loads and plays background music. Loading new music automatically stops the old one.

        Args:
            music_path (str): The file path to the music file.
            loops (int): The number of times to repeat the music. -1 means loop forever.
        """
        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.play(loops)
        except pygame.error as e:
            print(f"Error playing music from '{music_path}': {e}")

    def stop_music(self):
        """Stops the background music."""
        pygame.mixer.music.stop()

    def set_sfx_volume(self, volume):
        """
        Sets the base volume for all sound effects.

        Args:
            volume (float): A value from 0.0 (silent) to 1.0 (full volume).
        """
        self.sfx_volume = max(0.0, min(1.0, volume))

    def set_music_volume(self, volume):
        """
        Sets the volume for the background music.

        Args:
            volume (float): A value from 0.0 (silent) to 1.0 (full volume).
        """
        self.music_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.music_volume)