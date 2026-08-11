package main

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/sha512"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
)

const (
	PageSize  = 4096
	SaltSize  = 16
	IVSize    = 16
	HMACSize  = 64
	KeySize   = 32
	IterCount = 256000
)

// ── PBKDF2-HMAC-SHA512 (标准库实现，无外部依赖) ──
func pbkdf2(password, salt []byte, iter, keyLen int) []byte {
	prf := hmac.New(sha512.New, password)
	hashLen := prf.Size()
	numBlocks := (keyLen + hashLen - 1) / hashLen

	dk := make([]byte, 0, numBlocks*hashLen)
	buf := make([]byte, 4)

	for block := 1; block <= numBlocks; block++ {
		binary.BigEndian.PutUint32(buf, uint32(block))
		prf.Reset()
		prf.Write(salt)
		prf.Write(buf)
		T := prf.Sum(nil)
		U := make([]byte, len(T))
		copy(U, T)

		for i := 2; i <= iter; i++ {
			prf.Reset()
			prf.Write(U)
			U = prf.Sum(nil)
			for j := range T {
				T[j] ^= U[j]
			}
		}
		dk = append(dk, T...)
	}
	return dk[:keyLen]
}

func xorBytes(a, b []byte) []byte {
	r := make([]byte, len(a))
	for i := range a {
		r[i] = a[i] ^ b[i]
	}
	return r
}

func decryptPage(page, encKey []byte) ([]byte, error) {
	reserve := (IVSize + HMACSize + 15) / 16 * 16
	iv := page[PageSize-reserve : PageSize-reserve+IVSize]
	encData := page[SaltSize : PageSize-reserve]

	block, err := aes.NewCipher(encKey)
	if err != nil {
		return nil, err
	}

	mode := cipher.NewCBCDecrypter(block, iv)
	plaintext := make([]byte, len(encData))
	mode.CryptBlocks(plaintext, encData)
	return plaintext, nil
}

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintf(os.Stderr, "Usage: decrypt <key_hex> <db_path> [output_path]\n")
		os.Exit(1)
	}

	keyHex := os.Args[1]
	dbPath := os.Args[2]
	outputPath := dbPath + ".dec.db"
	if len(os.Args) >= 4 {
		outputPath = os.Args[3]
	}

	key, err := hex.DecodeString(keyHex)
	if err != nil {
		fmt.Fprintf(os.Stderr, "BAD_KEY: %v\n", err)
		os.Exit(1)
	}

	data, err := os.ReadFile(dbPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "READ_FAIL: %v\n", err)
		os.Exit(1)
	}

	pageCount := len(data) / PageSize
	salt := data[:SaltSize]
	encKey := pbkdf2(key, salt, IterCount, KeySize)
	macSalt := make([]byte, SaltSize)
	for i := range macSalt {
		macSalt[i] = salt[i] ^ 0x3a
	}
	macKey := pbkdf2(encKey, macSalt, 2, KeySize)

	_ = macKey // used for HMAC verification (skipped for now)
	fmt.Fprintf(os.Stderr, "DB: %s (%d pages)\n", filepath.Base(dbPath), pageCount)

	// First page: SQLite header + decrypted data
	page1 := data[:PageSize]
	plain1, err := decryptPage(page1, encKey)
	if err != nil {
		fmt.Fprintf(os.Stderr, "DECRYPT_FAIL: %v\n", err)
		os.Exit(1)
	}

	// Check if decryption is correct
	if string(plain1[:16]) != "SQLite format 3\x00" {
		fmt.Fprintf(os.Stderr, "FAIL: Expected SQLite header, got: %x\n", plain1[:16])
		fmt.Fprintf(os.Stderr, "Salt: %s\n", hex.EncodeToString(salt))
		fmt.Fprintf(os.Stderr, "EncKey: %s\n", hex.EncodeToString(encKey))
		// Try HMAC-SHA512 derived IV
		mac := hmac.New(sha512.New, macKey)
		pageBytes := make([]byte, 4)
		binary.BigEndian.PutUint32(pageBytes, 1)
		mac.Write(pageBytes)
		mac.Write(make([]byte, 12))
		iv2 := mac.Sum(nil)[:16]

		block, _ := aes.NewCipher(encKey)
		mode := cipher.NewCBCDecrypter(block, iv2)
		alt := make([]byte, len(page1[:PageSize-((IVSize+HMACSize+15)/16*16)]))
		mode.CryptBlocks(alt, page1[SaltSize:PageSize-((IVSize+HMACSize+15)/16*16)])
		fmt.Fprintf(os.Stderr, "Alt IV result: %x\n", alt[:32])
		os.Exit(1)
	}

	// Decrypt all pages
	out := make([]byte, 0, PageSize*pageCount)
	out = append(out, []byte("SQLite format 3\x00")...)
	out = append(out, plain1[SaltSize:]...)

	for i := 1; i < pageCount; i++ {
		page := data[i*PageSize : (i+1)*PageSize]
		plain, err := decryptPage(page, encKey)
		if err != nil {
			fmt.Fprintf(os.Stderr, "DECRYPT_FAIL page %d: %v\n", i, err)
			os.Exit(1)
		}
		out = append(out, plain...)
	}

	os.WriteFile(outputPath, out, 0644)
	fmt.Fprintf(os.Stderr, "OK: %s (%d bytes)\n", outputPath, len(out))
	fmt.Println("OK")
}
