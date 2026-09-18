-- Ekstre Çevir — üstüne bırakılan PDF'i Excel'e çevirip açar.
-- Uygulama, calistir.sh ile aynı klasörde durmalıdır (masaüstüne kısayol/alias konabilir).

on run
	try
		set secilenler to choose file with prompt "Excel'e çevrilecek PDF dosyasını seçin (ya da PDF'i simgenin üstüne bırakın):" of type {"com.adobe.pdf"} with multiple selections allowed
	on error number -128
		return
	end try
	cevir(secilenler)
end run

on open birakilanlar
	cevir(birakilanlar)
end open

on cevir(dosyalar)
	set klasor to do shell script "dirname " & quoted form of POSIX path of (path to me)
	set betik to klasor & "/calistir.sh"
	try
		do shell script "test -f " & quoted form of betik
	on error
		display dialog "calistir.sh bulunamadı." & return & return & "“Ekstre Çevir” uygulaması, programın klasöründen taşınmamalı. Masaüstüne koymak için uygulamanın kısayolunu (alias) oluşturun." buttons {"Tamam"} default button 1 with icon stop with title "Ekstre Çevir"
		return
	end try

	try
		do shell script "test -f " & quoted form of (klasor & "/.venv/.kurulum_tamam")
	on error
		display dialog "İlk kullanım: gerekli bileşenler kuruluyor." & return & "İnternet bağlantısı gerekir, 1-2 dakika sürebilir. Bittiğinde Excel kendiliğinden açılacak." buttons {"Tamam"} default button 1 with title "Ekstre Çevir" giving up after 6
	end try

	repeat with dosya in dosyalar
		set pdfYolu to POSIX path of dosya
		set dosyaAdi to do shell script "basename " & quoted form of pdfYolu
		try
			with timeout of 1800 seconds
				set excelYolu to do shell script "/bin/bash " & quoted form of betik & " --yol " & quoted form of pdfYolu
			end timeout
			do shell script "open " & quoted form of excelYolu
		on error hataMesaji number hataNo
			if hataNo is -128 then return
			display dialog "“" & dosyaAdi & "” çevrilemedi." & return & return & hataMesaji buttons {"Tamam"} default button 1 with icon caution with title "Ekstre Çevir"
		end try
	end repeat
end cevir
