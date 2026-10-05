# -*- coding: utf-8 -*-
# Nepali Reader for NVDA - opening PDFs that are "protected" only against editing/printing
# (standard security handler with an empty user password): RC4, AES-128 and AES-256.
# Pure Python (AES uses Windows' own crypto library when available). No NVDA dependencies.

import hashlib
import struct

PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")


def rc4(key, data):
	s = list(range(256))
	j = 0
	klen = len(key)
	for i in range(256):
		j = (j + s[i] + key[i % klen]) & 255
		s[i], s[j] = s[j], s[i]
	out = bytearray(len(data))
	i = j = 0
	for n, c in enumerate(data):
		i = (i + 1) & 255
		j = (j + s[i]) & 255
		s[i], s[j] = s[j], s[i]
		out[n] = c ^ s[(s[i] + s[j]) & 255]
	return bytes(out)


# ---------------------------------------------------------------- AES (FIPS-197)

def _xt(a):
	return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else a << 1


def _mul(a, b):
	r = 0
	while b:
		if b & 1:
			r ^= a
		a = _xt(a)
		b >>= 1
	return r


def _rotl(x, n):
	return ((x << n) | (x >> (8 - n))) & 0xFF


def _makeSbox():
	exp = [0] * 512
	log = [0] * 256
	x = 1
	for i in range(255):
		exp[i] = x
		log[x] = i
		x ^= _xt(x)  # multiply by 3, a generator
	for i in range(255, 512):
		exp[i] = exp[i - 255]
	sbox = [0] * 256
	inv = [0] * 256
	for i in range(256):
		v = 0 if i == 0 else exp[255 - log[i]]
		s = v ^ _rotl(v, 1) ^ _rotl(v, 2) ^ _rotl(v, 3) ^ _rotl(v, 4) ^ 0x63
		sbox[i] = s
		inv[s] = i
	return sbox, inv


_SBOX, _INV = _makeSbox()


_M9 = [_mul(x, 9) for x in range(256)]
_M11 = [_mul(x, 11) for x in range(256)]
_M13 = [_mul(x, 13) for x in range(256)]
_M14 = [_mul(x, 14) for x in range(256)]
_M2 = [_mul(x, 2) for x in range(256)]
_M3 = [_mul(x, 3) for x in range(256)]


def _expand(key):
	nk = len(key) // 4
	nr = nk + 6
	w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
	rcon = 1
	for i in range(nk, 4 * (nr + 1)):
		t = list(w[i - 1])
		if i % nk == 0:
			t = t[1:] + t[:1]
			t = [_SBOX[x] for x in t]
			t[0] ^= rcon
			rcon = _xt(rcon)
		elif nk > 6 and i % nk == 4:
			t = [_SBOX[x] for x in t]
		w.append([w[i - nk][k] ^ t[k] for k in range(4)])
	return [sum(w[4 * r:4 * r + 4], []) for r in range(nr + 1)]


def _encBlock(rk, b):
	s = [b[i] ^ rk[0][i] for i in range(16)]
	nr = len(rk) - 1
	for r in range(1, nr + 1):
		s = [_SBOX[x] for x in s]
		s = [s[0], s[5], s[10], s[15], s[4], s[9], s[14], s[3], s[8], s[13], s[2], s[7], s[12], s[1], s[6], s[11]]
		if r != nr:
			t = []
			for c in range(4):
				a0, a1, a2, a3 = s[4 * c:4 * c + 4]
				t += [_M2[a0] ^ _M3[a1] ^ a2 ^ a3, a0 ^ _M2[a1] ^ _M3[a2] ^ a3, a0 ^ a1 ^ _M2[a2] ^ _M3[a3], _M3[a0] ^ a1 ^ a2 ^ _M2[a3]]
			s = t
		k = rk[r]
		s = [s[i] ^ k[i] for i in range(16)]
	return bytes(s)


def _decBlock(rk, b):
	nr = len(rk) - 1
	s = [b[i] ^ rk[nr][i] for i in range(16)]
	for r in range(nr - 1, -1, -1):
		s = [s[0], s[13], s[10], s[7], s[4], s[1], s[14], s[11], s[8], s[5], s[2], s[15], s[12], s[9], s[6], s[3]]
		s = [_INV[x] for x in s]
		k = rk[r]
		s = [s[i] ^ k[i] for i in range(16)]
		if r:
			t = []
			for c in range(4):
				a0, a1, a2, a3 = s[4 * c:4 * c + 4]
				t += [_M14[a0] ^ _M11[a1] ^ _M13[a2] ^ _M9[a3], _M9[a0] ^ _M14[a1] ^ _M11[a2] ^ _M13[a3],
					_M13[a0] ^ _M9[a1] ^ _M14[a2] ^ _M11[a3], _M11[a0] ^ _M13[a1] ^ _M9[a2] ^ _M14[a3]]
			s = t
	return bytes(s)


def _winAes(key, iv, data, decrypt):
	"""AES-CBC through Windows bcrypt (fast); None when not available."""
	try:
		import ctypes
		from ctypes import wintypes
		bc = ctypes.WinDLL("bcrypt")
	except Exception:
		return None
	try:
		alg = ctypes.c_void_p()
		if bc.BCryptOpenAlgorithmProvider(ctypes.byref(alg), "AES", None, 0):
			return None
		mode = "ChainingModeCBC"
		buf = ctypes.create_unicode_buffer(mode)
		bc.BCryptSetProperty(alg, "ChainingMode", buf, ctypes.sizeof(buf), 0)
		hkey = ctypes.c_void_p()
		kb = ctypes.create_string_buffer(key, len(key))
		if bc.BCryptGenerateSymmetricKey(alg, ctypes.byref(hkey), None, 0, kb, len(key), 0):
			bc.BCryptCloseAlgorithmProvider(alg, 0)
			return None
		ivb = ctypes.create_string_buffer(iv, 16)
		inb = ctypes.create_string_buffer(data, len(data))
		out = ctypes.create_string_buffer(len(data))
		n = wintypes.ULONG()
		fn = bc.BCryptDecrypt if decrypt else bc.BCryptEncrypt
		st = fn(hkey, inb, len(data), None, ivb, 16, out, len(data), ctypes.byref(n), 0)
		bc.BCryptDestroyKey(hkey)
		bc.BCryptCloseAlgorithmProvider(alg, 0)
		if st:
			return None
		return out.raw[:n.value]
	except Exception:
		return None


def aesCbcDecrypt(key, iv, data):
	data = data[:len(data) - len(data) % 16]
	if not data:
		return b""
	r = _winAes(key, iv, data, True)
	if r is not None:
		return r
	rk = _expand(key)
	out = bytearray()
	prev = iv
	for i in range(0, len(data), 16):
		blk = data[i:i + 16]
		d = _decBlock(rk, blk)
		out += bytes(a ^ b for a, b in zip(d, prev))
		prev = blk
	return bytes(out)


def aesCbcEncrypt(key, iv, data):
	r = _winAes(key, iv, data, False)
	if r is not None:
		return r
	rk = _expand(key)
	out = bytearray()
	prev = iv
	for i in range(0, len(data), 16):
		blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
		prev = _encBlock(rk, blk)
		out += prev
	return bytes(out)


def _unpad(b):
	if b and 1 <= b[-1] <= 16 and len(b) >= b[-1]:
		return b[:-b[-1]]
	return b


# ---------------------------------------------------------------- standard security handler

class StandardDecryptor:
	def __init__(self, enc, fileId):
		"""enc: the resolved /Encrypt dictionary (str keys). Raises ValueError if a password is needed."""
		self.v = int(enc.get("V", 0) or 0)
		self.r = int(enc.get("R", 2) or 2)
		self.aes = False
		self.aes256 = False
		self.identity = False
		self.encryptMetadata = enc.get("EncryptMetadata", True) is not False
		length = int(enc.get("Length", 40) or 40)
		if self.v >= 4:
			cf = enc.get("CF") or {}
			name = enc.get("StmF") or "Identity"
			if name == "Identity":
				self.identity = True
			cfm = (cf.get(name) or {}).get("CFM")
			if cfm == "AESV2":
				self.aes = True
				length = 128
			elif cfm == "AESV3":
				self.aes = self.aes256 = True
				length = 256
			elif cfm == "V2":
				length = int((cf.get(name) or {}).get("Length", 16) or 16) * 8 if int((cf.get(name) or {}).get("Length", 16) or 16) <= 32 else int((cf.get(name) or {}).get("Length", 128))
		O = enc.get("O") or b""
		U = enc.get("U") or b""
		P = int(enc.get("P", 0) or 0) & 0xFFFFFFFF
		if self.r >= 5:
			self.key = self._key256(enc, U)
		else:
			n = max(5, length // 8) if self.r >= 3 else 5
			h = hashlib.md5(PAD + O[:32] + struct.pack("<I", P) + (fileId or b""))
			if self.r >= 4 and not self.encryptMetadata:
				h.update(b"\xff\xff\xff\xff")
			key = h.digest()[:n]
			if self.r >= 3:
				for _ in range(50):
					key = hashlib.md5(key).digest()[:n]
			self.key = key
			if not self._checkUser(U, fileId):
				raise ValueError("password required")

	def _checkUser(self, U, fileId):
		try:
			if self.r == 2:
				return rc4(self.key, PAD) == U[:32]
			h = hashlib.md5(PAD + (fileId or b"")).digest()
			x = rc4(self.key, h)
			for i in range(1, 20):
				x = rc4(bytes(k ^ i for k in self.key), x)
			return x[:16] == U[:16]
		except Exception:
			return True

	def _hash2B(self, pwd, salt, udata):
		k = hashlib.sha256(pwd + salt + udata).digest()
		if self.r == 5:
			return k
		i = 0
		while True:
			k1 = (pwd + k + udata) * 64
			e = aesCbcEncrypt(k[:16], k[16:32], k1)
			m = sum(e[:16]) % 3
			k = (hashlib.sha256, hashlib.sha384, hashlib.sha512)[m](e).digest()
			i += 1
			if i >= 64 and e[-1] <= i - 32:
				break
		return k[:32]

	def _key256(self, enc, U):
		UE = enc.get("UE") or b""
		pwd = b""
		check = self._hash2B(pwd, U[32:40], b"")
		if check[:32] != U[:32]:
			raise ValueError("password required")
		ik = self._hash2B(pwd, U[40:48], b"")
		return aesCbcDecrypt(ik, b"\0" * 16, UE[:32])

	def decrypt(self, num, gen, data):
		if self.identity or not data:
			return data
		if self.aes256:
			return _unpad(aesCbcDecrypt(self.key, data[:16], data[16:]))
		k = self.key + struct.pack("<I", num)[:3] + struct.pack("<I", gen)[:2]
		if self.aes:
			k += b"sAlT"
		k = hashlib.md5(k).digest()[:min(len(self.key) + 5, 16)]
		if self.aes:
			return _unpad(aesCbcDecrypt(k, data[:16], data[16:]))
		return rc4(k, data)
